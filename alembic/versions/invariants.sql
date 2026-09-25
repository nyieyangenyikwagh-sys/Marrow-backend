CREATE FUNCTION reject_immutable_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Ledger and audit records are immutable'; END;
$$;
-- SPLIT
CREATE TRIGGER ledger_immutable BEFORE UPDATE OR DELETE ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION reject_immutable_change();
-- SPLIT
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION reject_immutable_change();
-- SPLIT
CREATE FUNCTION protect_transaction() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Transactions cannot be deleted'; END IF;
  IF (to_jsonb(NEW) - ARRAY['status','completed_at','updated_at']) IS DISTINCT FROM
     (to_jsonb(OLD) - ARRAY['status','completed_at','updated_at']) THEN
    RAISE EXCEPTION 'Transaction financial fields are immutable';
  END IF;
  IF NEW.status <> OLD.status AND NOT (
      (OLD.status = 'PENDING' AND NEW.status IN ('COMPLETED','FAILED')) OR
      (OLD.status = 'COMPLETED' AND NEW.status = 'REVERSED')) THEN
    RAISE EXCEPTION 'Invalid transaction transition';
  END IF;
  IF NEW.completed_at IS DISTINCT FROM OLD.completed_at AND NOT
     (OLD.status = 'PENDING' AND NEW.status = 'COMPLETED' AND NEW.completed_at IS NOT NULL) THEN
    RAISE EXCEPTION 'Completion timestamp is immutable after posting';
  END IF;
  RETURN NEW;
END;
$$;
-- SPLIT
CREATE TRIGGER transaction_protected BEFORE UPDATE OR DELETE ON transactions
FOR EACH ROW EXECUTE FUNCTION protect_transaction();
-- SPLIT
CREATE FUNCTION validate_ledger_account() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM accounts WHERE id=NEW.account_id AND customer_id=NEW.customer_id
                 AND currency_code=NEW.currency_code) THEN
    RAISE EXCEPTION 'Ledger account ownership or currency mismatch';
  END IF;
  IF NEW.status <> 'COMPLETED' THEN RAISE EXCEPTION 'Only posted ledger entries are allowed'; END IF;
  RETURN NEW;
END;
$$;
-- SPLIT
CREATE TRIGGER ledger_account_guard BEFORE INSERT ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION validate_ledger_account();
-- SPLIT
CREATE FUNCTION verify_posting() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tid uuid; state text; n integer;
BEGIN
  IF TG_TABLE_NAME = 'transactions' THEN tid := NEW.id; ELSE tid := NEW.transaction_id; END IF;
  SELECT status::text INTO state FROM transactions WHERE id=tid;
  SELECT count(*) INTO n FROM ledger_entries WHERE transaction_id=tid;
  IF state IN ('COMPLETED','REVERSED') AND n < 2 THEN RAISE EXCEPTION 'Completed transaction needs ledger legs'; END IF;
  IF state IN ('PENDING','FAILED') AND n <> 0 THEN RAISE EXCEPTION 'Unposted transaction has ledger legs'; END IF;
  IF EXISTS (SELECT currency_code FROM ledger_entries WHERE transaction_id=tid GROUP BY currency_code
             HAVING sum(CASE WHEN entry_type='CREDIT' THEN amount ELSE -amount END) <> 0) THEN
    RAISE EXCEPTION 'Unbalanced transaction';
  END IF;
  RETURN NULL;
END;
$$;
-- SPLIT
CREATE CONSTRAINT TRIGGER balanced_ledger AFTER INSERT ON ledger_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_posting();
-- SPLIT
CREATE CONSTRAINT TRIGGER posted_transaction AFTER INSERT OR UPDATE ON transactions
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_posting();
