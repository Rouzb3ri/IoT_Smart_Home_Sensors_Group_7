"""Local dashboard and JSON endpoints. No services start on import."""
import cherrypy
from catalog_cli import CatalogManager
from config import ROOT
from shared_memory import control_sensor
from sensor_views import sensor_status


class DashboardWebServer:
    def __init__(self, catalog=None):
        self.catalog = catalog or CatalogManager()

    @cherrypy.expose
    def index(self):
        cherrypy.response.headers["Cache-Control"] = "no-store"
        return (ROOT / "dashboard.html").read_text(encoding="utf-8")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        cherrypy.response.headers["Cache-Control"] = "no-store"
        return sensor_status(self.catalog)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def control(self):
        if cherrypy.request.method != "POST":
            raise cherrypy.HTTPError(405, "Use POST")
        # The header forces browser cross-origin requests to preflight; no CORS is enabled.
        if cherrypy.request.headers.get("X-SmartHome-Client") != "dashboard":
            raise cherrypy.HTTPError(403, "Use the dashboard controls")
        payload = cherrypy.request.json
        if not isinstance(payload, dict):
            raise cherrypy.HTTPError(400, "Expected a JSON object")
        try:
            return control_sensor(payload.get("device_id"), payload.get("action"), self.catalog)
        except ValueError as error:
            raise cherrypy.HTTPError(400, str(error)) from error
