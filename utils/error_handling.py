import logging
from functools import wraps
from flask import jsonify

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except RuntimeError as e:
            logging.error(f"RuntimeError in {f.__name__}: {str(e)}")
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            logging.exception(f"Exception in {f.__name__}: {str(e)}")
            return jsonify({"error": "An unexpected error occurred."}), 500
    return decorated_function
