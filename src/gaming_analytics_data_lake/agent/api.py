import argparse
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from gaming_analytics_data_lake.agent.adapters.http import create_application
from gaming_analytics_data_lake.agent.bootstrap import build_agent


class LocalServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Lancer l’API locale de l’agent Gold.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        agent = build_agent()
    except ValueError as error:
        parser.error(str(error))

    with make_server(
        "127.0.0.1", args.port, create_application(agent), server_class=LocalServer
    ) as server:
        print(f"API Gold sur http://127.0.0.1:{server.server_port}/api/ask", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
