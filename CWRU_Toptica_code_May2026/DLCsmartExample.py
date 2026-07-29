from DLCsmartTHz_V3_0_0 import DLCsmartTHz, NetworkConnection

# This example needs the TOPTICA-LaserSDK:
# $pip install toptica-lasersdk

with DLCsmartTHz(NetworkConnection("127.0.0.1")) as dlc:
    print('Firmware Version :', dlc.general.fw_ver.get())
