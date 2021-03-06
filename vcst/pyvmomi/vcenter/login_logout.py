# Author: ybendre
# Test: login_logout
# This test will perform login-logout of vcenter

import json
import os
from pyVmomi import vim
from pyVim.connect import SmartConnect, SmartConnectNoSSL, Disconnect
import atexit
import argparse
import getpass

class Test:

    def __init__(self):
        self.vc=os.getenv("vcenter")
        if self.vc is None:
            self.logger.info("No vCenter provided, please set environment variable vcenter")
            return None

        self.username = os.getenv("vcuser")
        if self.username is None:
            self.username = "administrator@vsphere.local"

        self.password=os.getenv("vcpassword")
        if self.password is None:
            self.password = "Admin!23"

        self.port = os.getenv("port")
        if self.port is None:
            self.port = "443"
        self.mysession = None
        self.content = None

        # Function to get the vCenter server session

    def login(self):
        try:
            si = SmartConnectNoSSL(host=self.vc, user=self.username, pwd=self.password, port=self.port)
            self.mysession = si
            return True
        except Exception as e:
            print("Authentication failed")
            self.mysession = None
            return False

    def logout(self):
        try:
            Disconnect(self.mysession)
            return True
        except Exception as e:
            print("Logout failed")
            self.mysession = None
            return False


    def testSetup(self):
        return True

    def testTask(self):
        if self.login():
            if self.logout():
                return True
            else:
                return False
        else:
            return False
        

    def testCleanup(self):
        return True
