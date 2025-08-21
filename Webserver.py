import cherrypy
import sys
import os
sys.path.append(os.path.abspath(".."))
from shared_memory import shared_data, add_data

print(f"[APP] Shared data memory location: {id(shared_data)}")

class DashboardWebServer:

    @cherrypy.expose
    def index(self):
        html = """
        <html>
            <head>
                <title>Smart House Dashboard</title>
                <meta http-equiv="refresh" content="10">
                <style>
                    body { font-family: Arial; margin: 40px; background-color: #f5f5f5; }
                    table { border-collapse: collapse; width: 100%; background: white; }
                    th, td { border: 1px solid #aaa; padding: 8px; text-align: center; }
                    th { background-color: #444; color: white; }
                    h1 { color: #333; }
                </style>
            </head>
            <body>
                <h1>Live Sensor Data</h1>
                <table>
                    <tr>
                        <th>Timestamp</th>
                        <th>Device ID</th>
                        <th>Device Name</th>
                        <th>Measurement Type</th>
                        <th>Value</th>
                        <th>Unit</th>
                        <th>Room</th>
                        <th>Topic</th>
                    </tr>
        """

        
        for row in reversed(shared_data[-50:]):  
            html += f"""
                <tr>
                    <td>{row['Timestamp']}</td>
                    <td>{row['Device ID']}</td>
                    <td>{row['Device Name']}</td>
                    <td>{row['Measurement Type']}</td>
                    <td>{row['Value']}</td>
                    <td>{row['Unit']}</td>
                    <td>{row['Room']}</td>
                    <td>{row['Topic']}</td>
                </tr>
            """

        html += """
                </table>
            </body>
        </html>
        """
        print(f"[APP] Shared data has {len(shared_data)} rows")

        return html


if __name__ == '__main__':
    cherrypy.quickstart(DashboardWebServer(), '/', {
        '/': {
            'tools.sessions.on': True,
        }
    })

print(f"[APP] Shared data memory location: {id(shared_data)}")
