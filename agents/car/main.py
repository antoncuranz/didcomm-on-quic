import argparse
import asyncio
import logging

from agents.car.app import CarApp
from .agent import Agent

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

parser = argparse.ArgumentParser()

parser.add_argument(
    "ident",
    type=str,
    help="Agent identity (label)"
)
parser.add_argument(
    "--ip",
    default="localhost",
    help="External host IP",
)
parser.add_argument(
    "--ledger",
    default="http://test.bcovrin.vonx.io",
    help="Indy Ledger URL",
)
parser.add_argument(
    "-p",
    "--port",
    type=int,
    default=8020,
    help="Choose the starting port number to listen on",
)
parser.add_argument(
    "--receive-invitations",
    action="store_true"
)


async def main(args):
    agent = Agent(args.ident, args.ledger, http_port=args.port, external_host=args.ip,
                  receive_invitations=args.receive_invitations)
    app = CarApp(agent)

    try:
        await app.run_async()
    finally:
        await agent.terminate()


if __name__ == "__main__":
    asyncio.run(main(parser.parse_args()), debug=True)
