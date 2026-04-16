from flask import Blueprint

main = Blueprint('main', __name__)

from .blueprints.invoice import register_invoice_routes
from .blueprints.project import register_project_routes
from .blueprints.settings import register_settings_routes
from .blueprints.api import register_api_routes

register_invoice_routes(main)
register_project_routes(main)
register_settings_routes(main)
register_api_routes(main)
