Some micropython programs for a rpi pico to help triggering on communication.

To set up a python file into the pico, use something like this, so that it is called main on the other side:

```
mpytool -p /dev/ttyACM0 put trigger_swd_frame.py main.py
```