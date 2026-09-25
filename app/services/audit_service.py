import json
from app.models.audit import AuditLog


class AuditService:
    @staticmethod
    async def log_action(db, *, entity_type, entity_id, action, actor_id=None,
                         actor_type="system", old_values=None, new_values=None, **kwargs):
        def clean(value):
            return json.loads(json.dumps(value, default=str)) if value is not None else None
        row = AuditLog(entity_type=entity_type, entity_id=entity_id, action=action,
                       actor_id=actor_id, actor_type=actor_type,
                       old_values=clean(old_values), new_values=clean(new_values), **kwargs)
        db.add(row)
        await db.flush()
        return row
