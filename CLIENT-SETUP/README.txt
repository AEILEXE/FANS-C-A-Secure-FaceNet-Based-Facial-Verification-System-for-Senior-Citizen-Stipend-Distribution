================================================================
 FANS-C  |  Client Setup Package
 Run this once on each device that needs to access FANS-C.
================================================================


HOW TO RUN SETUP (3 steps)
---------------------------

  Step 1.  Make sure  rootCA.pem  is in this folder.
           (Your IT admin will provide this file.)

  Step 2.  Double-click:   trust-local-cert.bat

           A security prompt will appear — click "Yes" to allow it.
           Follow the steps on screen.
           When asked for the server IP address, enter the address
           your IT admin gave you (example: 192.168.1.77).

  Step 3.  When setup says "Setup complete!", open your browser and
           go to:     https://fans-barangay.local

That's it.  You do not need to run setup again on this device.


================================================================
 FOR IT ADMINISTRATORS — before distributing this package
================================================================

  1. On the SERVER, open PowerShell and run:
         mkcert -CAROOT
     This prints a folder path.

  2. Open that folder and copy   rootCA.pem   to a USB drive.

  3. Place   rootCA.pem   in this CLIENT-SETUP folder
     (same folder as trust-local-cert.bat).

  4. Copy this entire CLIENT-SETUP folder to each client device
     (via USB drive, shared folder, or email).


WHAT THE SETUP SCRIPT DOES
---------------------------
  - Installs the FANS-C server certificate so the browser trusts
    the secure HTTPS connection (no security warning).
  - Adds fans-barangay.local to the computer's address list so
    the browser can find the server by name.
  - Does NOT change any other system settings.
  - mkcert does NOT need to be installed on client devices.


TROUBLESHOOTING
---------------
Browser still shows a security warning after setup:
  -> Restart the browser completely and try again.
  -> Make sure rootCA.pem was copied from THIS server.

Cannot reach https://fans-barangay.local:
  -> Make sure you are connected to the same network as the server.
  -> Ask the IT admin for the correct server IP address.
  -> Check that the hosts file entry was added (the script does this).

For other issues, contact your IT administrator.

================================================================
