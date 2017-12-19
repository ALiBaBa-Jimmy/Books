# Common Source Code - trunk revision 38926, file revision 37279
### PRELOAD.PY
###
import sys, traceback, getopt
import time, string, popen2
import os
import flashdef,log
import preload_files

pgmname='preload'

class testexception(RuntimeError):
    pass


class tests:

    def __init__( self, parent=None ):
        self.parent = parent
        if self.parent != None:
            self.log = self.parent.log
            self.blade_test = self.parent.seq.blade_test
        else:
            self.log = log.log( )
        #
        #
        self.preload_timeout = 2000 * 60
        #
        ## Preload Methods
        self.winpe5 = 0
        self.winpe3 = 0
        self.winpe = 0
        self.linux = 0
        self.reboot = 0
        self.preload_required = 0 # Default is NOT to do preload
        self.ign_list =['i8042prt']
        return

    def preload(self):
        # Check to see if we should boot DOS/WINPE/Linux to do preload
        if os.path.exists('MoPSPrep.log'):
            if not os.path.exists('AODSTAT.DAT'):
                msg= 'MoPSPrep.log exists, but AODSTAT.DAT does not exist!'
                raise testexception,  msg
        if os.path.exists('AODSTAT.DAT'):
            f=open('AODSTAT.DAT','r')
            aod=f.read()
            f.close()
        elif os.path.exists( 'AOD.DAT'):
            f=open('AOD.DAT','r')
            aod=f.read()
            f.close()
        else:
            self.log.log( 'Did not find AOD.DAT or AODSTAT.DAT' )
            self.preload_required = 0
        if self.parent.cfgchk.preload_fc:
            self.preload_required = 1
        else:
            if aod.upper().find( 'PARTITION(' ) != -1:
                self.preload_required = 1
                if aod.upper().find( 'NODOWNLOAD=TRUE' ) != -1:
                    self.preload_required = 0
        if aod.upper().find( 'OSTYPE=LINUX' ) != -1:
            self.preload_required = 1
            self.linux = 1
        if aod.upper().find( 'OSTYPE=WINPE3' ) != -1:
            self.preload_required = 1
            self.winpe3 = 1
        if aod.upper().find( 'OSTYPE=WINPE5' ) != -1:
            self.preload_required = 1
            self.winpe3 = 1
            self.winpe5 = 1
        if self.preload_required:
            if self.parent.cfgchk.windows_fc:
                self.winpe = 1
            elif self.parent.cfgchk.linux_fc:
                self.linux = 1
            elif not self.linux and not self.winpe and not self.winpe3:
               msg = 'ERROR: Did not find a Linux or WinPE image. Assuming Custom WinPE image' 
               self.log.log( msg )
               self.winpe = 1
            msg = "Preload Type WinPE='%d' WinPE3='%d' Linux='%d' "
            msg = msg % (self.winpe, self.winpe3, self.linux)
            self.log.log( msg )
            self.preload_check_for_images( aod )
            if self.winpe3 and not self.linux:
               self.preload_winpe3()
            elif self.winpe and not self.linux:
               self.preload_winpe()
            elif self.linux:
               self.preload_linux()
            else:
               msg= 'Could not determine the preload method'
               raise testexception,  msg
        else:
            self.log.log( 'No Preload info found. Not Running Preload' )
            return('skip')
        #
        return
        
    def preload_linux(self):
        #
        #
        self.reboot = 0
        self.log.logp( 'Perform Preload in Linux' )
        #
        os.system( "rm -f PRELOAD.DON" )
        os.system( "rm -f error.log" )
        os.system( "rm -f ERROR.LOG" )
        os.system( "rm -f mops*.*" )
        os.system( "rm -f *.mop" )
        #
        self.preload_hdd_determine()
        #
        #self.mount_images()
        #r = os.system( 'tar -C / -xzf %s' % flashdef.linux_preload_zip )   ### Not needed. fdisk and sfdisk in RAMDISK
        self.mount_image_dir()
        #
        pre_msg = "\n Applying Preload Now !!! -- Do NOT turn system off -- \n"
        if not self.blade_test:
            self.parent.seq.statusbar.config( text=pre_msg,bg='yellow',fg='red')
        else:
            tst_msg = self.parent.seq.chassis_cmd( 'self.pstatus.cget( "text" )' )
            pre_msg = tst_msg + "\n\nApply\nPreload\n\n"
            self.parent.seq.chassis_cmd( 'self.pstatus.config( text=%s )' % repr(pre_msg) )
        #
        if not os.path.exists( flashdef.linux_mops64 ):
            msg  = "ERROR:'%s' not found " % flashdef.linux_mops64
            raise testexception, msg
        else:
            self.log.log( 'Found MOPS64.ZIP' )
        f=open( '/tmp/pre_load.sh','w')
        xcmd = 'PATH=$PATH:/image:/images:/image/dev:/'
        f.write( xcmd + "\n" )
        xcmd = "echo $PATH" 
        f.write( xcmd + "\n" )
        if "preload_tgz" in dir(flashdef) and "hana_preload" in dir( self.parent.cfgchk ):
            if "e1350" in dir(flashdef):
                self.log.log('Skipping preload on e1350 HANA systems')
                return('skip')
            for tgz in flashdef.preload_tgz:
                tgz_cmd = 'tar -C / -xzf %s \n' % tgz
                f.write( tgz_cmd )
            ## Create symbolic links to /dev/sda
            for dev in ('','1','2','3','4','5','6'):
                cmd = 'ln -s /dev/%s%s /dev/HANA%s' % (self.preload_hdd, dev, dev)
                self.log.log( cmd )
                self.runcmd( cmd )
        if "lvm_grub" in dir(flashdef):
            lvm_grub_cmd = 'tar -C / -xzf %s' % flashdef.lvm_grub
            f.write( lvm_grub_cmd + '\n' )
        cpcmd = "unzip -o %s -d /code" % flashdef.linux_mops64
        f.write( cpcmd + "\n" )
        if os.path.exists('AODSTAT.DAT'):
            cmd = "mops64.exe /noreboot /AOD=AODSTAT.DAT"
        else:
            cmd = "mops64.exe /noreboot /AOD=AOD.DAT"
        f.write( cmd + "\n" )
        f.write( 'echo PRELOAD_RTN=$?\n' )
        f.close()
        #
        f=open('/tmp/preload.sh','w')
        f.write( "rm -f /tmp/preload.log\n" )
        f.write( "/tmp/pre_load.sh 2>&1 | tee /tmp/preload.log\n" )
        f.write( "sleep 3\n" )
        f.close()
        #
        cmd = "chmod +x /tmp/pre_load.sh"
        r = os.system( cmd )
        if r != 0:
            msg  = "ERROR: '%s' cmd failed" % cmd
            raise testexception, msg
        cmd = "chmod +x /tmp/preload.sh"
        r = os.system( cmd )
        if r != 0:
            msg  = "ERROR: '%s' cmd failed" % cmd
            raise testexception, msg
        #
        cmd = "xterm -geometry 90x12+300+5 -e /tmp/preload.sh"
        runcmd = popen2.Popen4( cmd )
        #
        pre_start = time.time()
        pre_timeout = pre_start + self.preload_timeout
        while time.time() < pre_timeout:
            time.sleep(1)
            rtn = runcmd.poll()
            if rtn != -1:
                break
            if self.parent != None:
                pre_timer = int( time.time() - pre_start )
                if not self.blade_test:
                    stat_msg = pre_msg + ' %d min %02d sec ' % (pre_timer / 60, pre_timer % 60 )
                    self.parent.seq.statusbar.config( text=stat_msg )
                else:
                    stat_msg = pre_msg + '%d min\n%02d sec' % (pre_timer / 60, pre_timer % 60 )
                    self.parent.seq.chassis_cmd( 'self.pstatus.config( text=%s )' % repr(stat_msg) )
        #
        cpcmd = "cp /tmp/preload.log ."
        r = os.system( cpcmd )
        if r != 0:
            self.log.log( "ERROR %d %s" % ( r, cpcmd ) )
        #
        if rtn == -1:
            msg  = "ERROR: Preload TIMEOUT! (%dsec)" % ( self.preload_timeout )
            os.system( 'mops32.exe /RE' )
            os.system( 'mops32.exe /RE' )
            raise testexception, msg
        #
        response = string.strip( runcmd.fromchild.read() )
        print response
        #
        f=open('/tmp/preload.log','r')
        f_log = string.strip( f.read() )
        f.close()
        if string.find( f_log, 'PRELOAD_RTN=0' ) == -1:
            msg="ERROR: Preload failed!"
            msg += "\n See preload.log for MOPS output\n"
            pre_rtn = string.find( f_log, 'PRELOAD_RTN' )
            if pre_rtn != -1:
                msg+=" /tmp/preload.log = '%s'" % f_log[ pre_rtn: ]
            raise testexception,  msg
        #
        pre_msg = 'PRELOAD completed'
        self.log.logp( pre_msg )
        #
        if self.parent != None:
            if self.blade_test:
                self.parent.seq.chassis_cmd( 'self.pstatus.config( text=%s )' % repr(pre_msg) )
            else:
                self.parent.seq.statusbar.config( text=pre_msg, bg='white',fg='black' )
        #
        ###########################################################################
        #####  Audit Boot Setup           #########################################
        ###########################################################################
        ## Check boottype.dat. if WNTIBOOT is there we need to audit boot. 
        boot_types = ['WNTIBOOT', 'CANAUDIT', 'CUSTOMIMAGE' ]
        bootfile = "boottype.dat"
        if os.path.exists( bootfile ):
            boot_file = bootfile
        elif os.path.exists( bootfile.upper() ):
            boot_file = bootfile.upper()
        else:
            msg = 'Could not find %s' % bootfile
            raise testexception,msg
        f = open( boot_file,'r' )
        btype = f.readlines()
        f.close()
        for line in btype:
            boot_type = line.upper().strip()
            if boot_type in boot_types:
                self.log.log( "Found BOOTTYPE = '%s' " % boot_type )
            else:
                msg = 'Could not determine BOOT TYPE'
                raise testexception, msg
        if boot_type == 'CUSTOMIMAGE':
            if os.path.exists('modules.list.txt'):
                open('SAP_PRELOAD','w').write("This is a SAP Custom Preload")
                self.log.log( 'This is a SAP Custom image that needs to PXE boot VMWare' )
                ## Create PXE1TIME.CFG to PXE Boot VMWare/ EFI1TIME.CFG to Local Boot
                for files in ('EFI1TIME.LOG','EFI1TIME.CFG','PXE1TIME.CFG','PXE1TIME.LOG','vmware_preload.sh'):
                    if os.path.exists( files ):
                        os.remove( files )
                level_1 = os.environ[ 'L1SERVER' ]
                sut_mtsn = os.environ[ 'MTSN' ]
                vmware_common_dir = flashdef.vmware_common_dir.replace('/dfcxact/','')
                pxe1time = []
                pxe1time.append( 'TIMEOUT 8000\n' )
                pxe1time.append( 'LABEL VMWARE\n' )
                pxe1time.append( 'KERNEL %s/mboot.c32\n' % vmware_common_dir )
                pxe1time.append( 'APPEND -c %s/boot.cfg ' %  vmware_common_dir )
                pxe1time.append( 'APPEND MTSN=/dfcxact/mtsn/%s ' % sut_mtsn )
                pxe1time.append( 'L1SERVER=%s PRELOAD=%s ' % (level_1,self.imgsrvr) )
                pxe1time.append( 'ipappend 2\n' )
                pxe1time.append( 'DEFAULT VMWARE\n' )
                efi1time = []
                efi1time.append( 'TIMEOUT 8000\n' )
                efi1time.append( 'LABEL VMWARE\n' )
                efi1time.append( '    LOCALBOOT 0\n' )
                efi1time.append( 'DEFAULT VMWARE\n' )
                for line in pxe1time:
                    open('PXE1TIME.CFG','a').write( line )
                for line in efi1time:
                    open('EFI1TIME.CFG','a').write( line )
                ## Create vmware_preload.sh to run from within VMWare
                vmw_script = []
                if os.path.exists('sapbuild.sh'):
                    sapbuild_script = 'sapbuild.sh'
                else:
                    sapbuild_script = 'sapbuild'
                """ Old DS4 Script
                vmw_script.append( 'ftpget -u plclient -p client $L1 sapbuild.sh $MTSN/%s\n' % sapbuild_script )
                vmw_script.append( 'ftpget -u plclient -p client $L1 /tmp/modules.list.txt $MTSN/modules.list.txt\n' )
                vmw_script.append( 'chmod +x sapbuild.sh\n' )
                vmw_script.append( './sapbuild.sh\n' )
                vmw_script.append( 'echo PRELOAD_RTN=$? >> mfg_preload.log\n' )
                vmw_script.append( 'ftpput -p client -u plclient $L1 $MTSN/vm_preload.log /tmp/vm_preload-*.log\n' )
                vmw_script.append( 'ftpput -p client -u plclient $L1 $MTSN/mfg_preload.log mfg_preload.log\n' )
                """
                vmw_script.append( 'echo `date "+%d%b%Y %k:%M:%S"` " Copy sapbuild.sh to /tmp">> tester.log\n' )
                vmw_script.append( '/bin/cp /vmfs/volumes/$MTSN/sapbuild.sh /tmp/sapbuild.sh\n' )
                vmw_script.append( 'echo `date "+%d%b%Y %k:%M:%S"` " Copy modules.list.txt to /tmp" >> tester.log\n' )
                vmw_script.append( '/bin/cp /vmfs/volumes/$MTSN/modules.list.txt /tmp/modules.list.txt\n' )
                vmw_script.append( 'chmod +x /tmp/sapbuild.sh\n' )
                vmw_script.append( 'echo `date "+%d%b%Y %k:%M:%S"` " Running sapbuild.sh" >> tester.log\n' )
                vmw_script.append( '/tmp/sapbuild.sh\n' )
                vmw_script.append( 'echo PRELOAD_RTN=$? >> mfg_preload.log\n' )
                vmw_script.append( '/bin/cp /tmp/vm_preload-*.log /vmfs/volumes/$MTSN/vm_preload.log\n')
                vmw_script.append( 'echo `date "+%d%b%Y %k:%M:%S"` " sapbuild.sh exited" >> tester.log\n' )
                vmw_script.append( 'reboot -f\n' )
                for line in vmw_script:
                    open('vmware_preload.sh','a').write(line)
                self.parent.hdd.clear_partition()
                os.system("touch PRELOAD.DON")
                os.system("sync")
                pre_msg = 'Audit Boot Setup DONE'
                self.log.logp( pre_msg )
                self.log.logp( "Create linuxpre.flg" )
                f=open('linuxpre.flg','w')
                f.write( "preload setup: %s\r\n" % time.asctime() )
                f.close()
                #
                if not self.blade_test:
                    self.parent.seq.statusbar.config( text=pre_msg, bg='white',fg='black' )
                else:
                    self.parent.seq.chassis_cmd( 'self.pstatus.config( text=%s )' % repr(pre_msg) )
                self.reboot = 1
                return
            else:
                self.log.log( 'This is a Custom Image. No Audit Required' )
                os.system("touch PRELOAD.DON")
                os.system("sync")
                open('MOPS.PASS','w').write("Custom Image Passed")
                self.create_cksum()
                return
        ## Set up for Audit Boot
        ## Create MFGBOOT.BAT
        if 'schooner_preload' in dir( self.parent.cfgchk ):
            # Local Boot 1 TIME both EFI and PXELINUX.CFG
            self.runcmd( 'rm -f PXE1TIME.* EFI1TIME.* ' )
            f = open( 'EFI1TIME.CFG','w')
            f.write( 'LABEL HDD\n' )
            f.write( '   LOCALBOOT 0 \n' )
            f.write( 'DEFAULT HDD\n' )
            f.close()
            self.runcmd( 'cp EFI1TIME.CFG PXE1TIME.CFG' )
        elif 'hana_preload' in dir( self.parent.cfgchk ):
            if "e1350" in dir(flashdef):
                self.log.log('Skipping preload on e1350 HANA systems')
                return('skip')
            # Local Boot 1 TIME both EFI and PXELINUX.CFG
            self.runcmd( 'rm -f PXE1TIME.* EFI1TIME.* ' )
            f = open( 'EFI1TIME.CFG','w')
            f.write( 'LABEL HDD\n' )
            f.write( '   LOCALBOOT 0 \n' )
            f.write( 'DEFAULT HDD\n' )
            f.close()
            self.runcmd( 'cp EFI1TIME.CFG PXE1TIME.CFG' )
            mounts = self.runcmd( 'mount' )
            if mounts.lower().find( 'install1' ) != -1:
                self.runcmd( 'umount /install1')
            if mounts.lower().find( 'install2' ) != -1:
                self.runcmd( 'umount /install2')
        else:
            cmds = []
            cmds.append( 'c: \r\n' )
            cmds.append( 'cd \\ibmwork\r\n' )
            cmds.append( 'bootsig.com 1234 \r\n' )
            ##cmds.append( 'pause\r\n' )
            self.log.log( 'Create mfgboot.bat' )
            f = open( '/ibm/ibmwork/mfgboot.bat','w' )
            for cmd in cmds:
                f.write(cmd)
            f.close()
            ## Copy Files to /ibm/ibmwork
            files = ['bootsig.com' ]
            msg = ''
            for file in files:
                if not os.path.exists(flashdef.prod_dos_path + file):  ## Needs to be updated 
                    msg += '%s is missing\n' % file
                    self.log.log('%s is missing' % file )
                else:
                    self.log.log('%s found' % file )
                    os.system( 'cp %s%s /ibm/ibmwork' % (flashdef.prod_dos_path,file) )   ## Needs to be updated 
            if msg:
                raise testexception, msg
            ## Change Default in PXELINUX.CFG to PRELOAD_LINUX
            self.parent.seq.pxelinux_cfg( 'PRELOAD_LINUX' )
        os.system("touch PRELOAD.DON")
        os.system("sync")
        pre_msg = 'Audit Boot Setup DONE'
        self.log.logp( pre_msg )
        self.log.logp( "Create linuxpre.flg" )
        f=open('linuxpre.flg','w')
        f.write( "preload setup: %s\r\n" % time.asctime() )
        f.close()
        #
        if not self.blade_test:
            self.parent.seq.statusbar.config( text=pre_msg, bg='white',fg='black' )
        else:
            self.parent.seq.chassis_cmd( 'self.pstatus.config( text=%s )' % repr(pre_msg) )

        self.reboot = 1
        return

    def preload_winpe(self):
        self.log.logp( "preload setup" )
        #
        os.system("rm -f MOPS.PASS")
        os.system("rm -f yellowbang.log")
        os.system("rm -f MOPS.FAIL")
        os.system("rm -f mops.dat")
        #
        if 'wintools_zip' in dir(flashdef):
            f = open('tools.cmd','w')
            cmds = []
            for file in flashdef.linuxtools_zip:
                if not os.path.exists( file ):
                    msg = "%s does not exist!" % file
                    raise testexception,msg
            for file in flashdef.wintools_zip:
                cmds.append('UNZIP.EXE -o %s -d X:\\tools\\' % file )
            if os.path.exists( 'EFILINUX.CFG'):
                cmds.append( 'del EFILINUX.CFG' )
                cmds.append( 'copy EFI1TIME.CFG EFILINUX.CFG' )
            for cmd in cmds:
                f.write( cmd + '\r\n' )
                self.log.logp( cmd )
            f.close()
        # Must define bcd_file in flashdef.dat            
        self.winpe_bcd_file = flashdef.winpe_bcd_file
        self.log.logp( "WIN-PE BCD = %s" % self.winpe_bcd_file )
        #
        msg = "Create PXELINUX.MFG"
        self.log.logp( msg )
        cmd = "rm -f PXELINUX.MFG ; cp PXELINUX.CFG PXELINUX.MFG"
        self.runcmd( cmd, msg )
        if os.path.exists( 'EFILINUX.CFG'):
            msg = "Create EFILINUX.MFG"
            cmd = "rm -f EFILINUX.MFG ; cp EFILINUX.CFG EFILINUX.MFG"
            self.runcmd( cmd, msg )
        #
        self.log.logp( "Create PXELINUX.HDD" )
        f=open('PXELINUX.HDD','w')
        f.write( "LABEL HDD\n" )
        f.write( "    LOCALBOOT 0\n" )
        f.write( "DEFAULT HDD\n" )
        f.close()
        #
        if os.path.exists( 'EFILINUX.CFG'):
            msg = 'Create EFILINUX.CFG for WIN-PE'
            self.log.logp( msg )
            cmd = "rm -f EFI1TIME.LOG ; cp PXELINUX.HDD EFI1TIME.CFG"
            self.runcmd( cmd, msg )
        self.log.logp( "Create PXELINUX.PE2" )
        f=open('PXELINUX.PE2','w')
        f.write( "LABEL WINPE2\n" )
        if self.server_type == 'Linux':
            f.write( "    KERNEL pxe\pxeboot.n12.0\n" )
        else:
            f.write( "    KERNEL pxeboot.n12.0\n" )
        f.write( "    APPEND BCD=%s\n" % self.winpe_bcd_file )
        f.write( "DEFAULT WINPE2\n" )
        f.close()
        #
        msg = "Create PXE1TIME.CFG for WIN-PE"
        self.log.logp( msg )
        cmd = "rm -f PXE1TIME.LOG ; cp PXELINUX.PE2 PXE1TIME.CFG"
        self.runcmd( cmd, msg )
        #
        msg = 'Create EFILINUX.EFI for EFI Install'
        self.log.logp( msg )
        cmd = "rm -f EFILINUX.EFI"
        self.runcmd( cmd, msg )
        f=open('EFILINUX.EFI','w')
        f.write( "LABEL EFIPRELOAD\n" )
        f.write( "    KERNEL pxe/hddboot_winpe.efi\n" )
        f.write( "DEFAULT EFIPRELOAD\n" )
        f.close()
        #
        cmd = 'cp /code/asu64m.exe . '
        self.runcmd( cmd )
        f=open('winpe_audit_boot.cmd','w')
        if "Custom_Preload" in dir(self.parent.cfgchk) and self.parent.cfgchk.Custom_Preload:
            f.write('asu64m.exe set bootorder.bootorder "PXE Network=CD/DVD Rom=Floppy Disk=Hard Disk 0"\r\n')
        else:
            f.write('asu64m.exe set bootorder.bootorder "Hard Disk 0=PXE Network=CD/DVD Rom=Floppy Disk"\r\n') 
        f.close()
        f=open('rtn_2_ltp.cmd','w')
        f.write('cd \\ \r\n')
        f.write('label LENOVO_PRELOAD\r\n')
        f.write('rename IBMTOOLS LNVTOOLS\r\n')
        f.write('rename SYSLEVEL.IBM SYSLEVEL.LNV\r\n')
        f.write('rename IBM_Support LNV_Support\r\n')
        f.write('o:\\mtsn\\%s\\asu64m.exe set bootorder.bootorder "PXE Network=CD/DVD Rom=Floppy Disk=Hard Disk 0" --dumptofile\r\n' % os.environ[ 'MTSN' ] ) 
        f.write('del c:\\asulog\\asu*\r\n')
        f.write('rmdir c:\\asulog\r\n')
        f.close()
        self.log.logp( "Create preload.log" )
        f=open('preload.log','w')
        f.write( "preload setup: %s\r\n" % time.asctime() )
        f.close()
        #
        return
        
    def preload_winpe3(self):
        self.log.logp( "preload_winpe3: Preload from HDD booted WIM" )
        #
        os.system("rm -f MOPS.PASS")
        os.system("rm -f yellowbang.log")
        os.system("rm -f MOPS.FAIL")
        os.system("rm -f mops.dat")
        #
        self.preload_hdd_determine()
        #
        if 'wintools3_zip' in dir(flashdef):
            f = open('tools.cmd','w')
            cmds = []
            for file in flashdef.linuxtools3_zip:
                if not os.path.exists( file ):
                    msg = "%s does not exist!" % file
                    raise testexception,msg
            for file in flashdef.wintools3_zip:
                cmds.append('UNZIP.EXE -o %s -d X:\\tools\\' % file )
            for cmd in cmds:
                f.write( cmd + '\r\n' )
                self.log.logp( cmd )
            f.close()
        else:
            f = open('tools.cmd','w')
            cmds = []
            for file in preload_files.linuxtools3_zip:
                if not os.path.exists( file ):
                    msg = "%s does not exist!" % file
                    raise testexception,msg
            for file in preload_files.wintools3_zip:
                cmds.append('UNZIP.EXE -o %s -d X:\\tools\\' % file )
            for cmd in cmds:
                f.write( cmd + '\r\n' )
                self.log.logp( cmd )
            f.close()
        #
        msg = "Put WINPE on HDD"
        self.log.logp( msg )
        cmds = []
        if not os.path.exists( '/sbin/parted' ):
            cmds.append( "cp /dfcxact/pxe/parted /sbin/" )  # Should add to initrd
        cmds.append( "umount /hdd ; true" )
        # cmds.append( "dd if=/dev/zero bs=1k count=111k of=/dev/sda" )
        cmds.append( "parted -s /dev/%s mklabel gpt" % self.preload_hdd )
        cmds.append( "parted -s /dev/%s mkpartfs primary fat16 20kB 444MB" % self.preload_hdd )
        cmds.append( "sleep 60" )
        cmds.append( "partprobe" )
        cmds.append( "sleep 5" )
        cmds.append( "mount /dev/%s1 /hdd" % self.preload_hdd )
        cmds.append( "mkdir -p /hdd/boot" )
        cmds.append( "mkdir -p /hdd/efi/boot" )
        cmds.append( "mkdir -p /hdd/efi/microsoft/boot" )
        cmds.append( "mkdir -p /hdd/sources" )
        if not self.winpe5:
            wim = flashdef.wim3
            self.log.logp( "wim=%s" % flashdef.wim3 )
            cmds.append( "cp /dfcxact/pxe/boot.sdi    /hdd/boot/" )
            cmds.append( "cp /dfcxact/pxe/bootx64.efi /hdd/efi/boot/" )
            cmds.append( "cp %s /hdd/efi/microsoft/boot/bcd" % flashdef.winpe3_bcd_file )
            cmds.append( "cp %s /hdd/sources/boot.wim" % flashdef.wim3 )
        else:
            self.log.logp( "wim=%s" % preload_files.wim5 )
            wim = preload_files.wim5
            cmds.append( "cp %s /hdd/boot/boot.sdi" % preload_files.winpe5_boot_sdi )
            cmds.append( "cp %s /hdd/efi/boot/bootx64.efi" % preload_files.winpe5_bootx64 )
            cmds.append( "cp %s /hdd/efi/microsoft/boot/bcd" % preload_files.winpe5_bcd_file )
            cmds.append( "cp %s /hdd/sources/boot.wim" % preload_files.wim5 )
        cmds.append( "umount /hdd" )
        for cmd in cmds:
            self.log.logp(cmd)
            self.runcmd( cmd, msg, 180 )
        #
        msg = "Create EFILINUX.MFG"
        cmd = "rm -f EFILINUX.MFG ; cp EFILINUX.CFG EFILINUX.MFG"
        self.runcmd( cmd, msg )
        #
        msg = 'Create EFI1TIME.CFG for WINPE3'
        self.log.logp( msg )
        cmd = "rm -f EFI1TIME.LOG"
        self.runcmd( cmd, msg )
        f=open('EFI1TIME.CFG','w')
        f.write( "LABEL WINPE3\n" )
        f.write( "    KERNEL pxe/hddboot_winpe.efi\n" )
        f.write( "    APPEND WIM=%s\n" % wim )
        f.write( "DEFAULT WINPE3\n" )
        f.close()
        #
        cmd = 'cp /code/asu64m.exe . '
        self.runcmd( cmd )
        f=open('winpe_audit_boot.cmd','w')
        if "Custom_Preload" in dir(self.parent.cfgchk) and self.parent.cfgchk.Custom_Preload:
            f.write('asu64m.exe set bootorder.bootorder "PXE Network=CD/DVD Rom=Floppy Disk=Hard Disk 0"\r\n')
        else:
            f.write('asu64m.exe set bootorder.bootorder "Hard Disk 0=PXE Network=CD/DVD Rom=Floppy Disk"\r\n') 
        f.close()
        f=open('rtn_2_ltp.cmd','w')
        f.write('cd \\ \r\n')
        f.write('label LENOVO_PRELOAD\r\n')
        f.write('rename IBMTOOLS LNVTOOLS\r\n')
        f.write('rename SYSLEVEL.IBM SYSLEVEL.LNV\r\n')
        f.write('rename IBM_Support LNV_Support\r\n')
        f.write('o:\\mtsn\\%s\\asu64m.exe set bootorder.bootorder "PXE Network=CD/DVD Rom=Floppy Disk=Hard Disk 0" --dumptofile\r\n' % os.environ[ 'MTSN' ] ) 
        f.write('del c:\\asulog\\asu*\r\n')
        f.write('rmdir c:\\asulog\r\n')
        f.close()
        self.log.logp( "Create preload.log" )
        f=open('preload.log','w')
        f.write( "preload setup: %s\r\n" % time.asctime() )
        f.close()
        #
        return
        
    def preload_check_for_images( self,aod ):
        self.mount_image_dir()
        image_files = []
        image_files = os.listdir("/image/") + os.listdir("/images/")
        #
        cris = []
        msg = ''
        #
        for i in aod.split('\n'):
            if i.find(".CRI") != -1:
                cris.append( i.split("=")[1].strip() )
        for cri in cris:
            cri_found = 0
            for img_file in image_files:
                if cri.upper() == img_file.upper():
                    cri_found = 1
                    break
            if not cri_found:
                msg += "%s : file not found on preload server \n" % cri
        if msg != '':
            if self.server_type == 'Linux':
                raise testexception, msg
            else:
                self.log.log( msg )
                self.log.log( "Will request in WinPE boot" )
                return
        else:
            self.log.logp("All CRI files exist on preload server: %d CRIs in AOD" % len(cris) )
        return

    def preload_reboot(self):
        #
        if self.preload_required == 1:
            os.system( "echo ok > PRELOADSETUP.DON" )
            if self.linux:
                if not self.reboot:
                    return('skip')  ## Reboot not needed for Custom Linux Preload
            os.system( "echo ok > donpreloadsetup.ok" )
            if self.blade_test:
                self.preload_watchdog()
                time.sleep(10)
            else:
                reboot_msg = '\n Rebooting system'
                self.parent.seq.statusbar.config( text=reboot_msg+'\n ',bg='white',fg='blue' )
                for i in (1,2):
                    time.sleep(1)
                    reboot_msg += '.'
                    self.parent.seq.statusbar.config( text=reboot_msg+'\n' )
            os.system( self.parent.seq.reboot_cmd )
            time.sleep(20)
            #
            msg = "unit did not respond to reboot command"
            raise testexception, msg
        #
        else:
            return('skip')
        #
        return

    def preload_watchdog(self):
        #
        if str(flashdef.service_startup).find("bootseq=''") != -1:
            cmd = "self.watchdog( 'preload', 60*120, '', 0 )"
        else:
            cmd = "self.watchdog( 'preload', 60*120, 'NETWORK,HDD0,CDROM,FLOPPY', 0 )"
        self.log.logp( cmd )
        self.parent.seq.chassis_cmd( cmd )
        #
        return

    def preload_results( self ):
        self.log.log( 'Check Preload results' )
        os.system( 'rm -f PRELOADSETUP.DON' )
        if os.path.exists( 'linuxpre.flg' ):
            return( self.preload_results_linux() )
        if os.path.exists( 'donpreloadsetup.ok'):
            return( self.preload_results_winpe() )
        return

    def preload_results_winpe( self ):
        self.log.log( 'Check Preload results (WINPE)' )
        preload_passed = 0
        os.system("rm -f donpreloadsetup.ok")
        if os.path.exists( 'EFILINUX.MFG' ):
            cmd = '/bin/cp EFLINUX.MFG EFILINUX.CFG; rm -f EFILINUX.MFG' 
            self.runcmd( cmd, 'copy EFLINUX.MFG to EFILINUX.CFG' )
        if os.path.exists('MOPS.FAIL'):
            f=open('MOPS.FAIL','r')
            log=f.readlines()
            f.close()
            msg = ''
            for eachline in log:  
                msg += eachline             
            raise testexception,msg
        elif os.path.exists('MOPS.PASS'):            
            msg = "MOPS.PASS Exists..preload successful"
            self.log.logp( msg )
            if os.path.exists( 'yellowbang.log' ):
                msg = ''
                msg3 = ''
                f=open('yellowbang.log','r')
                ylog=f.readlines()
                f.close()
                self.log.logp( ylog[0].strip() )
                igndata = []
                ignfile = 'yellowbang.ign'
                if not os.path.exists( ignfile ):
                    ignfile = os.environ['PYTHONPATH']+'/'+ignfile
                if os.path.exists( ignfile ):
                    f=open( ignfile, 'r' )
                    igndata = f.readlines()
                    f.close()
                    pmsg = "Test using %s \n" % ignfile
                    for ea in igndata:
                        pmsg += ea
                    self.log.logp( pmsg )
                if len( ylog ) > 1:
                    i = 1
                    a = 1
                    b = 8
                    while b <= len(ylog):
                        ignore = 0
                        service = ylog[b-1].split()
                        if  len(service) > 1:
                            for entry in self.ign_list:
                                if entry == service[1]:
                                    ignore = 1
                        if not ignore:
                            i = 7
                            while i <= len( igndata ):
                                if ylog[a:b] == igndata[ i-7:i ]:
                                    ignore = 1
                                else:
                                    print ylog[a:b],igndata[i-7:i]
                                i += 7
                        for y in ylog[a:b]:
                            if ignore:
                                msg3 += y
                            else:
                                msg += y
                        a += 7
                        b += 7
                    if msg3:
                        msg2 = "Ignored Entry(s)\n"
                        self.log.log(msg2+msg3) 
                    if msg:
                        msg1 = "ERROR: Device Manager check FAILED during preload"
                        msg1 += "\n   See yellowbang.log\n"
                        msg1 += msg
                        raise testexception, msg1
                else:
                    self.log.logp( "yellowbang.log is empty" )
            preload_passed = 1
        else:
            msg = "Results file not found: MOPS.PASS or MOPS.FAIL"            
            raise testexception,msg
        self.create_cksum()
        return

    def preload_results_linux(self):
        sap_preload = 0
        self.log.log( 'Check Preload results (LINUX)' )
        #
        self.preload_hdd_determine()
        #
        if "schooner_preload" in dir( self.parent.cfgchk ):
            pass
        elif "hana_preload" in dir( self.parent.cfgchk ):
            pass
        elif os.path.exists('SAP_PRELOAD'):
            sap_preload = 1
            self.log.log('This is a SAP Preload')
        else:
            self.parent.seq.pxelinux_cfg( flashdef.pxe_label )   
        if not os.path.exists("PRELOAD.DON"):
            msg  = "PRELOAD.DON file not found, preload not on hdd!"
            raise testexception, msg 
        if os.path.exists("error.log"):
            msg  = "check error.log, preload unsuccessful!"
            raise testexception, msg
        if os.path.exists("ERROR.LOG"):
            msg  = "check ERROR.LOG, preload unsuccessful!"
            raise testexception, msg
        os.system( 'rm -f PRELOAD.DON' )
        boot_types = ['WNTIBOOT', 'CANAUDIT', 'CUSTOMIMAGE' ]
        bootfile = "boottype.dat"
        if os.path.exists( bootfile ):
            boot_file = bootfile
        elif os.path.exists( bootfile.upper() ):
            boot_file = bootfile.upper()
        else:
            msg = 'Could not find %s' % bootfile
            raise testexception,msg
        f = open( boot_file,'r' )
        btype = f.readlines()
        f.close()
        for line in btype:
            boot_type = line.upper().strip()
            if boot_type in boot_types:
                self.log.log( "Found BOOTTYPE = '%s' " % boot_type )
            else:
                msg = 'Could not determine BOOT TYPE'
                raise testexception, msg
        if boot_type == 'CUSTOMIMAGE':
            if sap_preload:
                pass
            else:
               self.log.log( 'This is a Custom Image. No Audit Required' )
               open('MOPS.PASS','w').write("Custom Image Passed")
               self.create_cksum()
               return
        if "schooner_preload" in dir( self.parent.cfgchk ):
            # Mount /dev/sda6 and check kickstart-stage2.log for + echo' '==> cleaning up...'
            # Memcache /dev/sda1
            dev =  self.parent.cfgchk.preload_check_dev 
            self.runcmd( 'mount /dev/%s /hdd' % dev )
            try:
                ks = open( '/hdd/root/kickstart-stage2.log' ).read()
            except:
                self.runcmd( 'umount /hdd' )
                msg = 'ERROR: Failed to open/find kickstart-stage2.log' 
                raise testexception, msg
            self.runcmd( 'umount /hdd' )
            #pen( 'kslog','w' ).write(ks)
            if ks.find( "+ echo '==> cleaning up...'" ) == -1:
                msg = "FAILED Audit Boot."
                raise testexception, msg
        elif "hana_preload" in dir( self.parent.cfgchk ):
            if "e1350" in dir(flashdef):
                self.log.log('Skipping preload on e1350 HANA systems')
                open('MOPS.PASS','w').write("HANA Preload not required on e1350 system")
                return('skip')
            self.runcmd( 'mount /dev/%s1 /hdd' %self.preload_hdd )
            try:
                y2log = open( '/hdd/var/log/YaST2/y2log' ).readlines()
            except:
                self.runcmd( 'umount /hdd' )
                msg = 'ERROR: Failed to open/find /var/log/YaST2/y2log'
                raise testexception, msg
            if y2log[-1].find( '[Y2Perl] YPerl.cc(destroy):164 Shutting down embedded Perl interpreter' ) == -1:
                self.runcmd( 'tar -czf hana_preload.tgz /hdd/var/log/YaST/* /hdd/var/adm/autoinstall/logs/*',"get preload results", 60)
                msg = "ERROR: Did not find right response in y2log"
                raise testexception, msg
            logs = os.listdir('/hdd/var/adm/autoinstall/logs')
            for log in logs:
                if log.lower().find('fail') != -1:
                    self.runcmd( 'tar -czf hana_preload.tgz /hdd/var/log/YaST/* /hdd/var/adm/autoinstall/logs/*',"get preload results", 60)
                    msg = "ERROR: Found Failed log in /var/adm/autoinstall/logs"
                    raise testexception,msg
            rtn = os.system( 'bash IPRA_post_preload.sh' )
            if rtn:
                msg = "ERROR: Service Partition still found. Preload Failed"
                raise testexception, msg
            self.runcmd( 'umount /hdd')
        elif sap_preload:
            ## Read mfg_preload.log and check for "SAP DISCOVERY PRELOAD PROCESS COMPLETED SUCCESSFULLY"
            if not os.path.exists('mfg_preload.log'):
                msg = "ERROR: can't find mfg_preload.log"
                raise testexception, msg
            data = open('mfg_preload.log').readlines()
            data1 = open('vm_preload.log').readlines()
            if data[-1].find("SAP DISCOVERY PRELOAD PROCESS COMPLETED SUCCESSFULLY") != -1:
                self.log.logp("Found SAP DISCOVERY PRELAOD PROCESS COMPLETED SUCCESSFULLY")
            elif data[-1].find("PRELOAD_RTN=0") != -1:
                self.log.logp("FOUND PRELOAD_RTN=0")
            else:
                msg =  'ERROR: SAP Preload preocess Failed(mfg_preload.log "SAP DISCOVERY PRELOAD PROCESS COMPLETED SUCCESSFULLY" Not Found)\n'
                msg += '               Or did not find PRELOAD_RTN=0\n'
                msg += '               Found "%s"' % data[-1]
                raise testexception, msg
            if data1[-1].find("SAP DISCOVERY PRELOAD PROCESS COMPLETED SUCCESSFULLY") == -1:
                msg = 'ERROR: SAP Preload preocess Failed(vm_preload.log "SAP DISCOVERY PRELOAD PROCESS COMPLETED SUCCESSFULLY" Not Found)'
                raise testexception, msg
        else:
            ## Now check to see if last 2 bytes of boot sig are 1234   
            changed_boot_sig = chr(0x12) + chr(0x34)  ## Read the changed Boot Sig
            orignal_boot_sig = chr(0x55) + chr(0xAA)  ## Write the original Boot sig
            f = open('/dev/%s','rb+' % self.preload_hdd )
            boot_sig = f.read(512)
            if boot_sig[-2:] == changed_boot_sig: ## Preload Passed else it failed
                new_boot_sig = boot_sig[:-2] + orignal_boot_sig
            else:
                msg = 'Failed AUDIT Boot.'
                raise testexception,msg
            f.seek(0x00)
            f.write(new_boot_sig)
            f.close()
        open('MOPS.PASS','w').write("Audit Boot Passed")
        self.log.log( 'Audit Boot Passed' )
        self.create_cksum()
        return

    def unmount_image_dir(self):
        cmds = []
        cmds.append('umount /image; true')
        cmds.append('umount /images; true')
        for cmd in cmds:
            self.runcmd(cmd)
        return

    def mount_image_dir(self):
        #
        self.imgsrvr = os.environ[ 'L1SERVER' ]
        passwrd = '-o username=plclient,password=client'
        f = open( '/proc/modules', 'r')
        lsmod_list = f.read()
        f.close()
        #
        if lsmod_list.find( 'cifs' ) != -1:
            mount_type = 'mount -t cifs '
        else:
            mount_type = 'smbmount '
        self.server_type = 'Windows'
        if os.path.exists( 'imgsrvr.txt' ): # Check in MTSN dir 
            imgsrvr_txt = 'imgsrvr.txt' 
        else:
            imgsrvr_txt = '/dfcxact/site/imgsrvr.txt'
        if os.path.exists( imgsrvr_txt ):
            self.log.logp( "Reading %s" % imgsrvr_txt )
            f=open( imgsrvr_txt )
            self.imgsrvr=f.readline().strip()
            passwrd = '-o username=l2plclient,password=L2client'
            f.close()
            self.server_type = 'Linux'
        else:
            msg = 'ERROR: Unable to find image server (imgsrvr.txt)'
            raise testexception, msg
        #
        self.log.logp( "server_type = %s" % self.server_type )
        cmd = 'mount'
        resp = self.runcmd( cmd, cmd )
        if resp.find( '/image ' ) == -1:
            r = os.system( 'mkdir -p /image' )
            cmd = '%s //%s/image /image ' % (mount_type,self.imgsrvr)
            self.log.logp( cmd )
            cmd += passwrd
            r = os.system( cmd )
            if r != 0:
                msg = 'ERROR: smbmount image dir FAILED'
                raise testexception, msg
        if resp.find( '/images ' ) == -1:
            r = os.system( 'mkdir -p /images' )
            cmd = '%s //%s/images /images ' % (mount_type,self.imgsrvr)
            self.log.logp( cmd )
            cmd += passwrd
            r = os.system( cmd )
            if r != 0:
                msg = 'ERROR: mount images dir FAILED'
                raise testexception, msg
        return

    def slp( self ):
        cmd = 'unzip -o %s -d /code; chmod +x /code/asu64m' % flashdef.asu_zip
        resp = self.runcmd( cmd, 'Unzip ASUM' )
        self.slp_needed = 0
        self.clear_slp()
        if self.parent.cfgchk.windows_fc:
            self.slp_needed = 1
            self.write_slp()
        self.verify_slp()
        return

    def clear_slp( self ):
        cmd = 'asu64m slp2 delete --kcs' 
        r = os.system( cmd )
        if r:
            if r == 2560:
                self.log.log( 'SLP appears to be cleared' )
            else:
                msg = 'ERROR: SLP Clear Faild'
                raise testexception, msg
        #cmd = 'asu64m slp2 oemid "IBM    "'
        #self.runcmd( cmd , 'Write OEM Table', 360 ) ## Used to make uEFI re-read the slic table
        return

    def write_slp( self ):
        ### New Lenovo Marker Files. Now in oa20_04032015.zip
        cmd = 'unzip -o %s -d /code' % preload_files.oa20_zip
        self.runcmd(cmd)
        #cmd = 'asu64m slp2 windowsmarker /code/OA20Marker.bin publickey /code/OA20PubKey.bin oemid "IBM   " oemtableid "SYSTEM_X" --kcs ' 
        cmd = 'asu64m slp2 windowsmarker /code/OA20Marker.bin publickey /code/OA20PubKey.bin oemid "LENOVO" oemtableid "SYSTEM_X" --kcs ' 
        resp = self.runcmd( cmd, 'Write SLP data', 360 )
        return

    def verify_slp( self ):
        ### New Lenovo Marker Files. Now in oa20_04032015.zip
        cmd = 'unzip -o %s -d /code' % preload_files.oa20_zip
        self.runcmd(cmd)
        cmd = 'asu64m slp2 extract --kcs'
        resp = self.runcmd( cmd, 'Extract SLP data', 360 ).split( '\n' )
        for line in resp:
            if line.find( 'OEM ID' ) != -1:
                oemid = line.split( '=' )[-1]
                self.log.log( "'%s'" % oemid.lstrip() )
            if line.find( 'OEM Table ID' ) != -1:
                oemtid = line.split( '=' )[-1]
                self.log.log( "'%s'" % oemtid.lstrip() )
        fail = 0
        fmsg = ''
        if self.slp_needed:
            #if oemid.lstrip() != 'IBM   ':
            if oemid.lstrip() != 'LENOVO':
                fail = 1
                fmsg += 'ERROR OEMID Incorrect\n'
            if oemtid.lstrip() != 'SYSTEM_X':
                fail = 1
                fmsg += 'ERROR OEM Table ID Incorrect\n'
            r = os.system( 'cmp SLP2Marker.dmp /code/OA20Marker.bin' )
            if r:
                fail = 1
                fmsg += 'ERROR SLP2Marker incorrect\n'
            r = os.system( 'cmp SLP2Key.dmp /code/OA20PubKey.bin' )
            if r:
                fail = 1
                fmsg += 'ERROR SLP2Key incorrect\n'
        else:
            if oemid != ' ':
                fail = 1
                fmsg += 'ERROR OEMID Incorrect\n'
            if oemtid != '':
                fail = 1
                fmsg += 'ERROR OEM Table ID Incorrect\n'
            for file in [ 'SLP2Marker.dmp', 'SLP2Key.dmp' ]:
                f = open( file )
                data = f.read()
                f.close()
                for byte in data:
                    if ord(byte) != 0:
                        fail = 1
                        fmsg += 'ERROR: %s incorrect\n' % file.split('.')[0]
                        break
        if fail:
            raise testexception, fmsg
        self.log.log( 'SLP Data correct' )
        return

    def verify(self):
        self.log.log('Verify Preload')
        if os.path.exists('MoPSPrep.log'):
            if not os.path.exists('AODSTAT.DAT'):
                msg= 'MoPSPrep.log exists, but AODSTAT.DAT does not exist!'
                raise testexception,  msg
        if os.path.exists('AODSTAT.DAT'):
            f=open('AODSTAT.DAT','r')
            aod=f.read()
            f.close()
        elif os.path.exists( 'AOD.DAT'):
            f=open('AOD.DAT','r')
            aod=f.read()
            f.close()
        else:
            self.log.log( 'Did not find AOD.DAT or AODSTAT.DAT' )
            self.preload_required = 0
        if self.parent.cfgchk.preload_fc:
            self.preload_required = 1
        else:
            if aod.upper().find( 'PARTITION(' ) != -1:
                self.preload_required = 1
                if aod.upper().find( 'NODOWNLOAD=TRUE' ) != -1:
                    self.preload_required = 0
        if aod.upper().find( 'OSTYPE=LINUX' ) != -1:
            self.preload_required = 1
        if aod.upper().find( 'OSTYPE=WINPE3' ) != -1:
            self.preload_required = 1
        if self.preload_required:
            if not os.path.exists('MOPS.PASS'):
                raise testexception,"ERROR: Preload Results not found"
            else:
                self.log.log("Preload results found PASSED")
        else:
            self.log.log("No Preload required")
        return

    def create_cksum( self ):
        if "val2" not in dir(self.parent):
            return
        # Read /proc/partitions and look for partion data
        pre_msg = 'Creating Checksum File'
        self.log.logp( pre_msg )
        #
        if self.parent != None:
            if self.blade_test:
                self.parent.seq.chassis_cmd( 'self.pstatus.config( text=%s )' % repr(pre_msg) )
            else:
                self.parent.seq.statusbar.config( text=pre_msg, bg='white',fg='black' )
        self.parent.val2.mfg_create_preload()
        return

    def mopsprep(self):
        import uutid
        mtm = uutid.rd( "MTM" )
        parts_list = 'SYSTEM.BMS'
        if os.path.exists(parts_list) and len(open(parts_list).readlines()) > 2:
            self.log.logp('SYSTEM.BMS file already contains Data.. No Need to run MoPSPrep')
            return('skip')
        self.mount_image_dir()
        part_list = open(parts_list,'w')
        part_list.write("BillofMatNum   OrdNum   CntrlNbr.\n")
        part_list.write("============   ======   ========.\n")
        part_list.close()
        for eachdev in self.parent.cfgchk.top_list:
            pn, locator, scsi_id_chan = eachdev
            if len(pn) > 7 and pn.find('_') != -1: # Accomodate New PN to FC 
                pn = pn.split('_')[0]
            if len(pn) > 7 and pn[:3] == '000': # Accomodate MFI pns
                pn = pn[3:]
            pn_line = "%s   TESTXX   XxXxXxXx\n" % pn.zfill(12) 
            open(parts_list,'a').write(pn_line)
        ##
        ## Requires libxml.. This is in rootimg20 +
        ## Check to see if the libxml rpm is installed, else install it now.
        rtn = os.system('rpm -qa |grep libxml2-python')
        if rtn: ## Need to install the rpm
            cmd = 'rpm -ivh %s' % preload_files.libxml
            self.runcmd(cmd)
        ## python2.6 /dfcxact/process/mopsprep.py -a AODSTAT.DAT -m {MTM} -i {Parts list File} -p /image/preload -s /image/preload/SWMATRIX.XML -v
        cmd = "python2.6 /dfcxact/process/mopsprep.py -a AODSTAT.DAT -m %s -i %s -p /image/preload -s /image/preload/SWMATRIX.XML -v" % (mtm, parts_list)
        resp = self.runcmd(cmd,'RUN MoPSPrep',60)
        open('MoPSPrep.log','w').write(resp)

    def preload_hdd_determine(self):
        if self.parent.lsi_sas.sg_map.has_key(0):
            self.preload_hdd = self.parent.lsi_sas.sg_map.get(0).split('/')[-1]
        else:
            self.parent.hdd.get_hdd_usb()
            if "vmware_fc" in dir(self.parent.cfgchk) and self.parent.cfgchk.vmware_fc:
                self.preload_hdd = self.parent.hdd.usb[0]
            else:
                self.preload_hdd = self.parent.hdd.hdd[0]
        self.log.log( 'Preload test will use HDD/USB %s' % self.preload_hdd )
        return

    def runcmd( self, cmd, cmdname=None, timeout=None ):
        resp = self.parent.misc.runcmd( cmd, cmdname, timeout )
        return(resp)

def main():
    """\
preload.py  -  eServer MFG preload methods'
    """
    print main.__doc__
    self = tests()
    self.create_cksum()

if __name__ == '__main__':
    main()


