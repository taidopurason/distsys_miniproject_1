import logging
from process import Process
from service import Resource

N = 3

resource_port = 18812
process_ports = tuple(18813 + i for i in range(N))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.getLogger("process").setLevel(logging.INFO)

resource = Resource(resource_port)
resource.start()

processes = []
for process_port in process_ports:
    process = Process(process_port, resource_port, list(set(process_ports) - {process_port}))
    process.daemon = True
    process.start()
    processes.append(process)

for t in processes:
    t.join()
resource.join()
