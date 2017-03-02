import sys
import os
import argparse
import shutil
import subprocess
from collections import OrderedDict
import struct
import urllib.request
import zipfile
import glob

class CEModDownloader():

    def __init__(self, steamcmd, modids, working_dir, mod_update):

        # I not working directory provided, check if CWD has a Conan Exiles server.
        self.working_dir = working_dir
        if not working_dir:
            self.working_dir_check()

        self.steamcmd = steamcmd  # Path to SteamCMD exe

        if not self.steamcmd_check():
            print("SteamCMD Not Found And We Were Unable To Download It")
            sys.exit(0)

        self.installed_mods = []  # List to hold installed mods
        self.map_names = []  # Stores map names from mod.info
        self.meta_data = OrderedDict([])  # Stores key value from modmeta.info
        self.temp_mod_path = os.path.join(os.path.dirname(self.steamcmd), r"steamapps\workshop\content\440900")

        self.prep_steamcmd()

        if mod_update:
            print("[+] Mod Update Is Selected.  Updating Your Existing Mods")
            self.update_mods()
            self.create_modlist()

        # If any issues happen in download and extract chain this returns false
        if modids:
            for mod in modids:
                if self.download_mod(mod):
                    if self.move_mod(mod):
                        print("[+] Mod {} Installation Finished".format(str(mod)))
                else:
                    print("[+] There was as problem downloading mod {}.  See above errors".format(str(mod)))
        self.create_modlist()

    def create_mod_name_txt(self, mod_folder, modid):
        print(os.path.join(mod_folder, self.map_names[0] + " - " + modid + ".txt"))
        with open(os.path.join(mod_folder, self.map_names[0] + ".txt"), "w+") as f:
            f.write(modid)

    def working_dir_check(self):
        print("[!] No working directory provided.  Checking Current Directory")
        print("[!] " + os.getcwd())
        if os.path.isdir(os.path.join(os.getcwd(), "ConanSandbox")):
            print("[+] Current Directory Has A Conan Exiles Server.  Using The Current Directory")
            self.working_dir = os.getcwd()
        else:
            print("[x] Current Directory Does Not Contain A Conan Exiles Server. Aborting")
            sys.exit(0)

    def steamcmd_check(self):
        """
        If SteamCMD path is provided verify that exe exists.
        If no path provided check TCAdmin path working dir.  If not located try to download SteamCMD.
        :return: Bool
        """

        # Check provided directory
        if self.steamcmd:
            print("[+] Checking Provided Path For SteamCMD")
            if os.path.isfile(os.path.join(self.steamcmd, "steamcmd.exe")):
                self.steamcmd = os.path.join(self.steamcmd, "steamcmd.exe")
                print("[+] SteamCMD Found At Provided Path")
                return True

        # Check TCAdmin Directory
        print("[+] SteamCMD Location Not Provided. Checking Common Locations")
        if os.path.isfile(r"C:\Program Files\TCAdmin2\Monitor\Tools\SteamCmd\steamcmd.exe"):
            print("[+] SteamCMD Located In TCAdmin Directory")
            self.steamcmd = r"C:\Program Files\TCAdmin2\Monitor\Tools\SteamCmd\steamcmd.exe"
            return True

        # Check working directory
        if os.path.isfile(os.path.join(self.working_dir, "SteamCMD\steamcmd.exe")):
            print("[+] Located SteamCMD")
            self.steamcmd = os.path.join(self.working_dir, "SteamCMD\steamcmd.exe")
            return True

        print("[+} SteamCMD Not Found In Common Locations. Attempting To Download")

        try:
            with urllib.request.urlopen("https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip") as response:
                if not os.path.isdir(os.path.join(self.working_dir, "SteamCMD")):
                    os.mkdir(os.path.join(self.working_dir, "SteamCMD"))

                steam_cmd_zip = os.path.join(self.working_dir, "steamcmd.zip")
                with open(steam_cmd_zip, "w+b") as output:
                    output.write(response.read())

                zip_file = zipfile.ZipFile(steam_cmd_zip)
                try:
                    zip_file.extractall(os.path.join(self.working_dir, "SteamCMD"))
                except zipfile.BadZipfile as e:
                    print("[x] Failed To Extract steamcmd.zip. Aborting")
                    print("[x] Error: " + e)
                    sys.exit()

        except urllib.request.HTTPError as e:
            print("[x] Failed To Download SteamCMD. Aborting")
            print("[x] ERROR: " + e)
            return False

        self.steamcmd = os.path.join(self.working_dir, r"SteamCMD\steamcmd.exe")

        return True

    def prep_steamcmd(self):
        """
        Delete steamapp folder to prevent Steam from remembering it has downloaded this mod before
        This is mainly for game hosts.  Example, hosts using TCAdmin have one SteamCMD folder. If mod was downloaded
        by another customer SteamCMD will think it already exists and not download again.
        :return:
        """

        steamapps = os.path.join(os.path.dirname(self.steamcmd), "steamapps")

        if os.path.isdir(steamapps):
            print("[+] Removing Steamapps Folder")
            try:
                shutil.rmtree(steamapps)
            except OSError:
                """
                If run on a TCAdmin server using TCAdmin's SteamCMD this may prevent mod from downloading if another
                user has downloaded the same mod.  This is due to SteamCMD's cache.  It will think this mod has is
                already installed and up to date.
                """
                print("[x] Failed To Remove Steamapps Folder. This is normally okay.")
                print("[x] If this is a TCAdmin Server and using the TCAdmin SteamCMD it may prevent mod from downloading")

    def update_mods(self):
        self.build_list_of_mods()
        if self.installed_mods:
            for mod in self.installed_mods:
                print("[+] Updating Mod " + mod)
                if not self.download_mod(mod):
                    print("[x] Error Updating Mod " + mod)
        else:
            print("[+] No Installed Mods Found.  Skipping Update")

    def build_list_of_mods(self):
        """
        Build a list of all installed mods by grabbing all file names from the mod folder
        :return:
        """
        if not os.path.isdir(os.path.join(self.working_dir, "ConanSandbox\Mods")):
            return
        for curdir, dirs, files in os.walk(os.path.join(self.working_dir, "ConanSandbox\Mods")):
            for d in files:
                self.installed_mods.append(d)
            break

    def download_mod(self, modid):
        """
        Launch SteamCMD to download ModID
        :return:
        """
        print("[+] Starting Download of Mod " + str(modid))
        args = []
        args.append(self.steamcmd)
        args.append("+login anonymous")
        args.append("+workshop_download_item")
        args.append("440900")
        args.append(modid)
        args.append("+quit")
        subprocess.call(args, shell=True)

        return True 


    def move_mod(self, modid):
        """
        Move mod from SteamCMD download location to the Conan Exiles server.
        It will delete an existing mod with the same ID
        :return:
        """

        conan_mod_folder = os.path.join(self.working_dir, "ConanSandbox\Mods")
        output_dir = os.path.join(conan_mod_folder)
        source_dir = os.path.join(self.temp_mod_path, modid)

        # TODO Need to handle exceptions here
        if not os.path.isdir(conan_mod_folder):
            print("[+] Creating Directory: " + conan_mod_folder)
            os.mkdir(conan_mod_folder)

        print("[+] Moving Mod Files To: " + output_dir)
        for pak_file in glob.iglob(source_dir + '\*.pak'):
            shutil.copy2(pak_file, output_dir)
            return True
    
    def create_modlist(self):
        conan_mod_folder = os.path.join(self.working_dir, "ConanSandbox\Mods")
        print('[+] Creating modlist.txt in ConanSandbox\Mods')
        os.chdir(conan_mod_folder)
        modfiles = glob.glob ('*.pak')
        with open ('modlist.txt', 'w') as in_files:
            for eachfile in modfiles: in_files.write(eachfile+'\n')
            return True
        


def main():
    parser = argparse.ArgumentParser(description="A utility to download Conan Exiles Mods via SteamCMD")
    parser.add_argument("--workingdir", default=None, dest="workingdir", help="Game server home directory.  Current Directory is used if this is not provided")
    parser.add_argument("--modid", nargs="+", default=None, dest="modids", help="ID of Mod To Download")
    parser.add_argument("--steamcmd", default=None, dest="steamcmd", help="Path to SteamCMD")
    parser.add_argument("--update", default=None, action="store_true", dest="mod_update", help="Update Existing Mods.  ")

    args = parser.parse_args()

    if not args.modids and not args.mod_update:
        print("[x] No Mod ID Provided and Update Not Selected.  Aborting")
        print("[?] Please provide a Mod ID to download or use --update to update your existing mods")
        sys.exit(0)

    CEModDownloader(args.steamcmd, args.modids, args.workingdir, args.mod_update)



if __name__ == '__main__':
    main()
