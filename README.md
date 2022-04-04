# Ricart-Agrawala algorithm
Distributed Systems Mini-Project 1

---

## Requirements
* Python==3.8
* rpyc==5.0.1
  * ```pip install rpyc==5.0.1```

---

## Instructions

Run the program with:

```
python main.py N
```

where ```N``` is the number of processes to be created.

By default the RPC server of the resource (critical section) is assigned the port of ```18812```. 
Processes are assigned ports ```port_resource + 1```, ```port_resource + 2```,```...``` , ```port_resource + N```,
where ```N``` is the number of processes created.

The ports can changed, for example:
```
python main.py 3 --resource-port 18817 --process-ports 18820 18830 18840
```

When started, the program asks for user input. Valid inputs are:
* ```List``` - lists processes with teir statuses
* ```time-cs <t:int>``` - sets ```t_cs```; process uses resource for random amount of time selected from ```[10, t]```.
* ```time-p <t:int>``` - sets ```t_p```; process waits for random amount of time selected from ```[5, t]``` before requesting a resource.
* ```exit``` - exits the program

### Video Demonstration


https://user-images.githubusercontent.com/42523949/161621033-21d2506c-87f7-487a-bca6-4c1ee84a52f4.mp4



