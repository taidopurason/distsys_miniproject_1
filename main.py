import logging
import sys

import argparse

from process import Process
from resource import Resource

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ricart-Agrawala algorithm')
    parser.add_argument('n_procs', metavar='N', type=int, help="The number of processes to create.")
    parser.add_argument('--resource-port', type=int, default=18812, help="Resource port")
    parser.add_argument(
        '--process-ports',
        type=int,
        nargs="*",
        default=None,
        help="List of ports assigned to processes. If specified, number of arguments must equal N"
    )
    parser.add_argument('--logfile', type=str, help="If specified, logs process events to the file given.")

    args = parser.parse_args()
    N = args.n_procs

    resource_port = args.resource_port
    process_ports = tuple(args.process_ports) if args.process_ports is not None else tuple(
        resource_port + i + 1 for i in range(N))

    if len(process_ports) != N:
        raise ValueError("Process ports do not match with the number of processes.")

    id_to_port = {i: port for i, port in enumerate(process_ports)}

    # for better understanding of what is happening in processes
    if args.logfile is not None:
        logging.basicConfig(
            filename=args.logfile,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logging.getLogger("process").setLevel(logging.INFO)
        logging.getLogger("resource").setLevel(logging.INFO)

    resource = Resource(resource_port)
    resource.daemon = True
    resource.start()

    processes = []
    for pid in id_to_port.keys():
        process = Process(pid, resource_port, id_to_port)
        process.daemon = True
        process.start()
        processes.append(process)

    while True:
        arguments = input("Input command: ").split(" ")
        command = arguments[0]

        if len(arguments) > 2:
            print("Too many arguments")
        elif command == "List" or command == "list":
            for p in processes:
                print(f"P{p.id}, {p.state.value}")
        elif command == "time-cs":
            try:
                resource.set_time(int(arguments[1]))
            except Exception as e:
                print(e)
        elif command == "time-p":
            try:
                for p in processes:
                    p.set_time(int(arguments[1]))
            except Exception as e:
                print(e)
        elif command == "exit":
            sys.exit(0)
        else:
            print("Unrecognized command")
            print("Valid commands are:\n\tList,\ttime-cs <int>,\ttime-p <int>,\texit")
