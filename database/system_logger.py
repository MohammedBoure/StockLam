# database/system_logger.py

import json
import inspect
import functools
import logging
from contextvars import ContextVar
from .base import Database

logger = logging.getLogger("JEWELLERY_SYS")

active_user_id = ContextVar("active_user_id", default=None)

def determine_action_type(func_name: str) -> str:
    """تحليل اسم الدالة وتصنيفها، وتجاهل القراءة تماماً"""
    name = func_name.lower()
    
    if any(name.startswith(p) for p in ["add_", "create_", "insert_"]):
        return "CREATE"
    elif any(name.startswith(p) for p in ["update_", "edit_", "modify_", "set_"]):
        return "UPDATE"
    elif any(name.startswith(p) for p in ["delete_", "remove_", "drop_", "clear_"]):
        return "DELETE"
    
    # أي شيء آخر (بما فيها get_ أو fetch_) يتم تجاهله نهائياً
    return "IGNORE"

def log_methods(module_name=None):
    """
    الديكوراتور: يقبل تمرير اسم مخصص مثل @log_methods("Devises")
    """
    def decorator(cls):
        # استخدام الاسم الممرر، وإذا كان فارغاً نستخدم اسم الكلاس
        mod_name = module_name or cls.__name__
        
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value) and not attr_name.startswith("_"):
                
                action_type = determine_action_type(attr_name)
                
                # تغليف الدوال المسموحة فقط (إنشاء، تعديل، حذف)
                if action_type != "IGNORE":
                    setattr(cls, attr_name, _wrap_method(attr_value, mod_name, attr_name, action_type))
                    
        return cls
    return decorator

def _wrap_method(func, module_name, action_name, action_type):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        
        # إذا فشلت العملية أو أرجعت None، لا نسجلها
        if result is False or result is None:
            return result

        # سحب المتغيرات الممررة للدالة
        sig = inspect.signature(func)
        bound_args = sig.bind(self, *args, **kwargs)
        bound_args.apply_defaults()
        
        details = {k: v for k, v in bound_args.arguments.items() if k != 'self'}
        
        # حفظ الـ ID الجديد في حال كانت العملية CREATE
        if isinstance(result, int) and not isinstance(result, bool):
             details['generated_id'] = result

        uid = active_user_id.get()
        if uid:
            # تنسيق اسم العملية ليظهر بشكل احترافي في الواجهة
            formatted_action = f"[{action_type}] {action_name}()"
            _insert_log(uid, module_name, formatted_action, details)
            
        return result
    return wrapper

def _insert_log(user_id, module, action, details):
    db = Database()
    try:
        details_json = json.dumps(details, ensure_ascii=False, default=str)
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO SystemLogs (user_id, module, action, details, ip_address) 
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (user_id, module, action, details_json, "127.0.0.1"))
    except Exception as e:
        logger.error(f"Failed to auto-log {action} in {module}: {e}")