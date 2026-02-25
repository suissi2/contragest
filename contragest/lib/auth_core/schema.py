from sqlalchemy import MetaData
from .models import create_auth_tables

def init_auth_schema(engine, base):
    """
    Initializes authentication tables.
    :param engine: SQLAlchemy Engine
    :param base: SQLAlchemy Declarative Base (should mixin UserMixin)
    """
    create_auth_tables(engine, base)
