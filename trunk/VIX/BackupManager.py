import Components.Task
from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Pixmap import MultiPixmap, Pixmap
from Components.config import configfile , config, ConfigYesNo, ConfigSubsection, getConfigListEntry, ConfigSelection, ConfigText, ConfigClock, ConfigNumber, NoSave
from Components.ConfigList import ConfigListScreen
from Components.Harddisk import harddiskmanager
from Components.Language import language
from Components.Sources.StaticText import StaticText
from Components.FileList import MultiFileSelectList
from Components.ScrollLabel import ScrollLabel
from Screens.Screen import Screen
from Components.Console import Console
from Screens.Console import Console as RestoreConsole
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Tools.Directories import pathExists, fileExists, resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_PLUGIN, SCOPE_CURRENT_SKIN, SCOPE_METADIR
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer, quitMainloop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, eListboxPythonMultiContent, eListbox, gFont, getDesktop, ePicLoad
from ServiceReference import ServiceReference
from os import path, system, unlink, stat, mkdir, popen, makedirs, chdir, getcwd, listdir, rename, remove, access, W_OK, R_OK, F_OK, statvfs
import datetime
from shutil import rmtree, move, copy
from time import localtime, time, strftime, mktime, sleep
from datetime import date
from enigma import eTimer

autoBackupManagerTimer = None

def BackupManagerautostart(reason, session=None, **kwargs):
	"called with reason=1 to during /sbin/shutdown.sysvinit, with reason=0 at startup?"
	global autoBackupManagerTimer
	global _session
	now = int(time())
	if reason == 0:
		print "[BackupManager] AutoStart Enabled"
		if session is not None:
			_session = session
			if autoBackupManagerTimer is None:
				autoBackupManagerTimer = AutoBackupManagerTimer(session)
	else:
		print "[BackupManager] Stop"
		autoBackupManagerTimer.stop()        

class VIXBackupManager(Screen):
	skin = """<screen name="VIXBackupManager" position="center,center" size="560,400" title="Backup Manager" flags="wfBorder" >
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" />
		<ePixmap pixmap="skin_default/buttons/key_menu.png" position="0,40" size="35,25" alphatest="blend" transparent="1" zPosition="3" />
		<ePixmap pixmap="skin_default/buttons/key_info.png" position="40,40" size="35,25" alphatest="blend" transparent="1" zPosition="3" />
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand" />
		<widget name="backupstatus" position="10,370" size="400,30" font="Regular;20" zPosition="5" />
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""


	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Backup Manager"))

		self['lab1'] = Label()
		self["backupstatus"] = Label()
		self["key_red"] = Button(_("Refresh List"))
		self["key_green"] = Button()
		self["key_yellow"] = Button(_("Restore"))
		self["key_blue"] = Button(_("Delete"))

		self.BackupRunning = False
		self.onChangedEntry = [ ]
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.backupRunning)
		self.activityTimer.start(10)

		if BackupTime > 0:
			backuptext = _("Next Backup: ") + strftime("%c", localtime(BackupTime))
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def backupRunning(self):
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			jobname = str(job.name)
			if jobname.startswith('BackupManager'):
				self.BackupRunning = True
		if self.BackupRunning:
			self["key_green"].setText(_("View Progress"))
		else:
			self["key_green"].setText(_("New Backup"))
		self.activityTimer.startLongTimer(5)

	def refreshUp(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if fil.endswith('.tar.gz'):
				self.emlist.append(fil)
		self.emlist.sort()
		self["list"].setList(self.emlist)
		self["list"].show()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveUp)

	def refreshDown(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if fil.endswith('.tar.gz'):
				self.emlist.append(fil)
		self.emlist.sort()
		self["list"].setList(self.emlist)
		self["list"].show()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveDown)

	def selectionChanged(self):
		for x in self.onChangedEntry:
			x()
		
	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))

	def showJobView(self, job):
		from Screens.TaskView import JobView
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job)
	
	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def populate_List(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if pathExists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.backupmanager.backuplocation.setChoices(imparts)

		if config.backupmanager.backuplocation.value.startswith('/media/net/'):
			mount1 = config.backupmanager.backuplocation.value.replace('/','')
			mount1 = mount1.replace('medianet','/media/net/')
			mount = config.backupmanager.backuplocation.value, mount1
		else:
			mount = config.backupmanager.backuplocation.value, config.backupmanager.backuplocation.value
		hdd = '/media/hdd/','/media/hdd/'
		if mount not in config.backupmanager.backuplocation.choices.choices:
			if hdd in config.backupmanager.backuplocation.choices.choices:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "TimerEditActions"],
					{
						'cancel': self.close,
						'red': self.populate_List,
						'green': self.GreenPressed,
						'yellow': self.keyResstore,
						'blue': self.keyDelete,
						"menu": self.createSetup,
						"up": self.refreshUp,
						"down": self.refreshDown,
						'log': self.showLog,
					}, -1)

				self.BackupDirectory = '/media/hdd/backup/'
				config.backupmanager.backuplocation.value = '/media/hdd/'
				config.backupmanager.backuplocation.save
				self['lab1'].setText(_("The chosen location does not exist, using /media/hdd") + _("\nSelect a backup to Restore / Delete:"))
			else:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "TimerEditActions"],
					{
						'cancel': self.close,
						"menu": self.createSetup,
						'log': self.showLog,
					}, -1)

				self['lab1'].setText(_("Device: None available") + _("\nSelect a backup to Restore / Delete:"))
		else:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "TimerEditActions"],
				{
					'cancel': self.close,
					'red': self.populate_List,
					'green': self.GreenPressed,
					'yellow': self.keyResstore,
					'blue': self.keyDelete,
					"menu": self.createSetup,
					"up": self.refreshUp,
					"down": self.refreshDown,
					'log': self.showLog,
				}, -1)

			self.BackupDirectory = config.backupmanager.backuplocation.value + 'backup/'
			self['lab1'].setText(_("Device: ") + config.backupmanager.backuplocation.value + _("\nSelect a backup to Restore / Delete:"))

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			images = listdir(self.BackupDirectory)
			del self.emlist[:]
			for fil in images:
				if fil.endswith('.tar.gz'):
					self.emlist.append(fil)
			self.emlist.sort()
			self["list"].setList(self.emlist)
			self["list"].show()
		except:
			self['lab1'].setText(_("Device: ") + config.backupmanager.backuplocation.value + _("\nthere was a problem with this device, please reformat and try again."))

	def createSetup(self):
		self.session.openWithCallback(self.setupDone, VIXBackupManagerMenu)

	def showLog(self):
		self.session.open(VIXBackupManagerLogView)

	def setupDone(self):
		self.populate_List()
		self.doneConfiguring()
		
	def doneConfiguring(self):
		now = int(time())
		if config.backupmanager.schedule.value:
			if autoBackupManagerTimer is not None:
				print "[BackupManager] Backup Schedule Enabled at", strftime("%c", localtime(now))
				autoBackupManagerTimer.backupupdate()
		else:
			if autoBackupManagerTimer is not None:
				global BackupTime
				BackupTime = 0
				print "[BackupManager] Backup Schedule Disabled at", strftime("%c", localtime(now))
				autoBackupManagerTimer.backupstop()
		if BackupTime > 0:
			backuptext = _("Next Backup: ") + strftime("%c", localtime(BackupTime))
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))

	def keyDelete(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to delete this backup:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDelete, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Remove Confirmation"))
		else:
			self.session.open(MessageBox, _("You have no backup to delete."), MessageBox.TYPE_INFO, timeout = 10)

	def doDelete(self, answer):
		if answer is True:
			self.sel = self['list'].getCurrent()
			self["list"].instance.moveSelectionTo(0)
			remove(self.BackupDirectory + self.sel)
		self.populate_List()

	def GreenPressed(self):
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			jobname = str(job.name)
			if jobname.startswith('BackupManager'):
				self.BackupRunning = True
		if self.BackupRunning:
			self.showJobView(job)
		else:
			self.keyBackup()

	def keyBackup(self):
		message = _("Are you ready to create a backup ?")
		ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Backup Confirmation"))
 
	def doBackup(self,answer):
		if answer is True:
			self.BackupFiles = BackupFiles(self.session)
			Components.Task.job_manager.AddJob(self.BackupFiles.createBackupJob())
			self.BackupRunning = True
			self["key_green"].setText(_("View Progress"))
			self["key_green"].show()

	def keyResstore(self):
		self.sel = self['list'].getCurrent()
		if not self.BackupRunning:
			if self.sel:
				message = _("Are you sure you want to restore this backup:\n ") + self.sel
				ybox = self.session.openWithCallback(self.doRestore, MessageBox, message, MessageBox.TYPE_YESNO)
				ybox.setTitle(_("Restore Confirmation"))
			else:
				self.session.open(MessageBox, _("You have no backups to restore."), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.session.open(MessageBox, _("Backup in progress,\nPlease for it to finish, before trying again"), MessageBox.TYPE_INFO, timeout = 10)

	def doRestore(self,answer):
		if answer is True:
			self.RestoreConsole = Console()
			if path.exists("/proc/stb/vmpeg/0/dst_width"):
				self.commands = ["tar -xzvf " + self.BackupDirectory + self.sel + " -C /", "echo 0 > /proc/stb/vmpeg/0/dst_height", "echo 0 > /proc/stb/vmpeg/0/dst_left", "echo 0 > /proc/stb/vmpeg/0/dst_top", "echo 0 > /proc/stb/vmpeg/0/dst_width"]
			else:
				self.commands = ["tar -xzvf " + self.BackupDirectory + self.sel + " -C /"]
			self.RestoreConsole.eBatch(self.commands, self.doRestorePlugins1, debug=True)

	def doRestorePlugins1(self, extra_args):
		self.RestoreConsole = Console()
		self.RestoreConsole.ePopen('opkg list-installed', self.doRestorePlugins2)

	def doRestorePlugins2(self, result, retval, extra_args):
		if retval == 0:
			if fileExists('/tmp/ExtraInstalledPlugins'):
				pluginlist = file('/tmp/ExtraInstalledPlugins').readlines()
				plugins = []
				for line in result.split('\n'):
					if line:
						parts = line.strip().split()
						plugins.append(parts[0])
				output = open('/tmp/trimedExtraInstalledPlugins','a')
				for line in pluginlist:
					if line:
						parts = line.strip().split()
						if parts[0] not in plugins:
							output.write(parts[0] + '\n')
				output.close()
				self.doRestorePluginsQuestion()

	def doRestorePluginsQuestion(self, extra_args = None):
		plugintmp = file('/tmp/trimedExtraInstalledPlugins').read()
		pluginslist = plugintmp.replace('\n',' ')
		if pluginslist:
			message = _("Restore wizard has detected that you had extra plugins installed at the time of you backup, Do you want to reinstall these plugins ?")
			ybox = self.session.openWithCallback(self.doRestorePlugins3, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Re-install Plugins"))
		else:
			self.RestoreConsole = Console()
			self.RestoreConsole.ePopen("killall -9 enigma2")

	def doRestorePlugins3(self, answer):
		if answer is True:
			plugintmp = file('/tmp/trimedExtraInstalledPlugins').read()
			pluginslist = plugintmp.replace('\n',' ')
			self.commands = ["opkg update", "opkg install " + pluginslist, 'rm -f /tmp/ExtraInstalledPlugins', 'rm -f /tmp/trimedExtraInstalledPlugins']
			self.RestoreConsole.eBatch(self.commands,self.doRestorePlugins4, debug=True)
		else:
			self.RestoreConsole = Console()
			self.RestoreConsole.ePopen("killall -9 enigma2")

	def doRestorePlugins4(self, result):
		self.RestoreConsole = Console()
		self.RestoreConsole.ePopen("killall -9 enigma2")




	def myclose(self):
		self.close()

class BackupSelection(Screen):
	skin = """
		<screen name="BackupSelection" position="center,center" size="560,400" title="Select files/folders to backup">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget name="checkList" position="5,50" size="550,250" transparent="1" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText()
		
		self.selectedFiles = config.backupmanager.backupdirs.value
		defaultDir = '/'
		self.filelist = MultiFileSelectList(self.selectedFiles, defaultDir )
		self["checkList"] = self.filelist
		
		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ShortcutActions"],
		{
			"cancel": self.exit,
			"red": self.exit,
			"yellow": self.changeSelectionState,
			"green": self.saveSelection,
			"ok": self.okClicked,
			"left": self.left,
			"right": self.right,
			"down": self.down,
			"up": self.up
		}, -1)
		if not self.selectionChanged in self["checkList"].onSelectionChanged:
			self["checkList"].onSelectionChanged.append(self.selectionChanged)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		idx = 0
		self["checkList"].moveToIndex(idx)
		self.setWindowTitle()
		self.selectionChanged()

	def setWindowTitle(self):
		self.setTitle(_("Select files/folders to backup"))

	def selectionChanged(self):
		current = self["checkList"].getCurrent()[0]
		if current[2] is True:
			self["key_yellow"].setText(_("Deselect"))
		else:
			self["key_yellow"].setText(_("Select"))
		
	def up(self):
		self["checkList"].up()

	def down(self):
		self["checkList"].down()

	def left(self):
		self["checkList"].pageUp()

	def right(self):
		self["checkList"].pageDown()

	def changeSelectionState(self):
		self["checkList"].changeSelectionState()
		self.selectedFiles = self["checkList"].getSelectedList()

	def saveSelection(self):
		self.selectedFiles = self["checkList"].getSelectedList()
		config.backupmanager.backupdirs.value = self.selectedFiles
		config.backupmanager.backupdirs.save()
		config.backupmanager.save()
		config.save()
		self.close(None)

	def exit(self):
		self.close(None)

	def okClicked(self):
		if self.filelist.canDescent():
			self.filelist.descent()


class VIXBackupManagerMenu(ConfigListScreen, Screen):
	skin = """
		<screen name="VIXBackupManagerMenu" position="center,center" size="500,285" title="Backup Manager Setup">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
			<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget name="config" position="10,45" size="480,150" scrollbarMode="showOnDemand" />
			<widget name="HelpWindow" pixmap="skin_default/vkey_icon.png" position="445,385" zPosition="1" size="500,285" transparent="1" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/key_text.png" position="430,5" zPosition="4" size="35,25" alphatest="on" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.skin = VIXBackupManagerMenu.skin
		self.skinName = "VIXBackupManagerMenu"
		Screen.setTitle(self, _("Backup Manager Setup"))
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self.createSetup()
		
		self["actions"] = ActionMap(["SetupActions", 'ColorActions', 'VirtualKeyboardActions'],
		{
			"ok": self.keySave,
			"cancel": self.keyCancel,
			"red": self.keyCancel,
			"green": self.keySave,
			"yellow": self.chooseFiles,
			'showVirtualKeyboard': self.KeyText
		}, -2)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))
		self["key_yellow"] = Button(_("Choose Files"))

	def createSetup(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if pathExists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.backupmanager.backuplocation.setChoices(imparts)
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Backup Location"), config.backupmanager.backuplocation))
		self.list.append(getConfigListEntry(_("Folder prefix"), config.backupmanager.folderprefix))
		self.list.append(getConfigListEntry(_("Schedule Backups"), config.backupmanager.schedule))
		if config.backupmanager.schedule.value:
			self.list.append(getConfigListEntry(_("Time of Backup to start"), config.backupmanager.scheduletime))
			self.list.append(getConfigListEntry(_("Repeat how often"), config.backupmanager.repeattype))
		self["config"].list = self.list
		self["config"].setList(self.list)

	# for summary:
	def changedEntry(self):
		if self["config"].getCurrent()[0] == "Schedule Backups":
			self.createSetup()
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def KeyText(self):
		if self['config'].getCurrent():
			if self['config'].getCurrent()[0] == "Folder prefix":
				from Screens.VirtualKeyBoard import VirtualKeyBoard
				self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title = self["config"].getCurrent()[0], text = self["config"].getCurrent()[1].getValue())

	def VirtualKeyBoardCallback(self, callback = None):
		if callback is not None and len(callback):
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

	def saveAll(self):
		for x in self["config"].list:
			x[1].save()
		configfile.save()

	# keySave and keyCancel are just provided in case you need them.
	# you have to call them by yourself.
	def keySave(self):
		self.saveAll()
		self.close()
	
	def cancelConfirm(self, result):
		if not result:
			return

		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def keyCancel(self):
		if self["config"].isChanged():
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close()

	def chooseFiles(self):
		self.session.openWithCallback(self.backupfiles_choosen,BackupSelection)

	def backupfiles_choosen(self, ret):
		self.backupdirs = ' '.join( config.backupmanager.backupdirs.value )
		config.backupmanager.backupdirs.save()
		config.plugins.configurationbackup.save()
		config.save()

class VIXBackupManagerLogView(Screen):
	skin = """
<screen name="VIXBackupManagerLogView" position="center,center" size="560,400" title="Backup Log" >
	<widget name="list" position="0,0" size="560,400" font="Regular;16" />
</screen>"""
	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		self.skinName = "VIXBackupManagerLogView"
		self["list"] = ScrollLabel(config.backupmanager.lastlog.value)
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
		{
			"cancel": self.cancel,
			"ok": self.cancel,
			"up": self["list"].pageUp,
			"down": self["list"].pageDown
		}, -2)

	def cancel(self):
		self.close()

class AutoBackupManagerTimer:
	def __init__(self, session):
		self.session = session
		self.backuptimer = eTimer() 
		self.backuptimer.callback.append(self.BackuponTimer)
		self.backupactivityTimer = eTimer()
		self.backupactivityTimer.timeout.get().append(self.backupupdatedelay)
		now = int(time())
		global BackupTime
		if config.backupmanager.schedule.value:
			print "[BackupManager] Backup Schedule Enabled at ", strftime("%c", localtime(now))
			if now > 1262304000:
				self.backupupdate()
			else:
				print "[BackupManager] Backup Time not yet set."
				BackupTime = 0
				self.backupactivityTimer.start(36000)
		else:
			BackupTime = 0
			print "[BackupManager] Backup Schedule Disabled at", strftime("(now=%c)", localtime(now))
			self.backupactivityTimer.stop()

	def backupupdatedelay(self):
		self.backupactivityTimer.stop()
		self.backupupdate()

	def getBackupTime(self):
		backupclock = config.backupmanager.scheduletime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, backupclock[0], backupclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def backupupdate(self, atLeast = 0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		#print '[BackupManager] BACKUP TIME',BackupTime
		#print '[BackupManager] NOW TIME',now
		#print '[BackupManager] ATLEAST',atLeast
		#print '[BackupManager] NOW + ATLEAST', (now + atLeast)
		#print '[BackupManager] BACKUP TIME - NOW', (BackupTime - now)
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				if config.backupmanager.repeattype.value == "daily":
					BackupTime += 24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 24*3600
					#BackupTime += 8*60
					#print '[BackupManager] BACKUP TIME 2:',BackupTime
					#print '[BackupManager] NOW 2:',now
					#while (int(BackupTime)-30) < now:
						#print '[BackupManager] YES BT is Less Now'
						#BackupTime += 8*60
						#print '[BackupManager] BACKUP TIME 2:',BackupTime
				elif config.backupmanager.repeattype.value == "weekly":
					BackupTime += 7*24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 7*24*3600
				elif config.backupmanager.repeattype.value == "monthly":
					BackupTime += 30*24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 30*24*3600
			next = BackupTime - now
			self.backuptimer.startLongTimer(next)
		else:
		    	BackupTime = -1
		print "[BackupManager] Backup Time set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
		return BackupTime

	def backupstop(self):
	    self.backuptimer.stop()

	def BackuponTimer(self):
		self.backuptimer.stop()
		now = int(time())
		wake = self.getBackupTime()
		# If we're close enough, we're okay...
		atLeast = 0
		if wake - now < 60:
			print "[BackupManager] Backup onTimer occured at", strftime("%c", localtime(now))
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("Your box is about to run a full image backup, this can take about 6 minutes to complete,\ndo you want to allow this?")
				ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle('Scheduled Backup.')
			else:
				print "[BackupManager] in Standby, so just running backup", strftime("%c", localtime(now))
				self.doBackup(True)
		else:
			print '[BackupManager] Where are not close enough', strftime("%c", localtime(now))
			self.backupupdate(60)
					
	def doBackup(self, answer):
		now = int(time())
		if answer is False:
			if config.backupmanager.backupretrycount.value < 2:
				print '[BackupManager] Number of retries',config.backupmanager.backupretrycount.value
				print "[BackupManager] Backup delayed."
				repeat = config.backupmanager.backupretrycount.value
				repeat += 1
				config.backupmanager.backupretrycount.value = repeat
				BackupTime = now + (int(config.backupmanager.backupretry.value) * 60)
				print "[BackupManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
				self.backuptimer.startLongTimer(int(config.backupmanager.backupretry.value) * 60)
			else:
				atLeast = 60
				print "[BackupManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout = 10)
				config.backupmanager.backupretrycount.value = 0
				self.backupupdate(atLeast)
		else:
			print "[BackupManager] Running Backup", strftime("%c", localtime(now))
			self.BackupFiles = BackupFiles(self.session)
			Components.Task.job_manager.AddJob(self.BackupFiles.createBackupJob())

class BackupFiles(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.Stage1Completed = False
		self.Stage2Completed = False
		self.Stage3Completed = False
		self.Stage4Completed = False
		self.Stage5Completed = False

	def createBackupJob(self):
		job = Components.Task.Job(_("BackupManager"))

		task = Components.Task.PythonTask(job, _("Starting..."))
		task.work = self.JobStart
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Starting..."), timeoutCount=30)
		task.check = lambda: self.Stage1Completed
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Renaming old backup..."))
		task.work = self.Stage2
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Renaming old backup..."), timeoutCount=30)
		task.check = lambda: self.Stage2Completed
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Creating list of instlled plugins..."))
		task.work = self.Stage3
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Creating list of instlled plugins..."), timeoutCount=30)
		task.check = lambda: self.Stage3Completed
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Backing up files..."))
		task.work = self.Stage4
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Backing up files..."), timeoutCount=600)
		task.check = lambda: self.Stage4Completed
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Backup Complete..."))
		task.work = self.BackupComplete
		task.weighting = 1

		return job

	def JobStart(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if pathExists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.backupmanager.backuplocation.setChoices(imparts)

		if config.backupmanager.backuplocation.value.startswith('/media/net/'):
			mount1 = config.backupmanager.backuplocation.value.replace('/','')
			mount1 = mount1.replace('medianet','/media/net/')
			mount = config.backupmanager.backuplocation.value, mount1
		else:
			mount = config.backupmanager.backuplocation.value, config.backupmanager.backuplocation.value
		hdd = '/media/hdd/','/media/hdd/'
		if mount not in config.backupmanager.backuplocation.choices.choices:
			if hdd in config.backupmanager.backuplocation.choices.choices:
				config.backupmanager.backuplocation.value = '/media/hdd/'
				config.backupmanager.backuplocation.save
				self.BackupDevice = config.backupmanager.backuplocation.value
				print "[BackupManager] Device: " + self.BackupDevice
				self.BackupDirectory = config.backupmanager.backuplocation.value + 'backup/'
				print "[BackupManager] Directory: " + self.BackupDirectory
				print "The chosen location does not exist, using /media/hdd"
			else:
				print "Device: None available"
		else:
			self.BackupDevice = config.backupmanager.backuplocation.value
			print "[BackupManager] Device: " + self.BackupDevice
			self.BackupDirectory = config.backupmanager.backuplocation.value + 'backup/'
			print "[BackupManager] Directory: " + self.BackupDirectory

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
		except Exception,e:
			print str(e)
			print "Device: " + config.backupmanager.backuplocation.value + ", i don't seem to have write access to this device."

		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail)/(1024*1024)
		if int(free) < 50:
			self.session.open(MessageBox, _("The backup location does not have enough freespace."), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.Stage1Complete()

	def Stage1Complete(self):
		self.Stage1Completed = True

	def Stage2(self):
		self.BackupConsole = Console()
		self.backupdirs = ' '.join(config.backupmanager.backupdirs.value)
		print '[BackupManager] Renaming old backup'
		if fileExists(self.BackupDirectory + config.backupmanager.folderprefix.value + '-' + 'enigma2settingsbackup.tar.gz'):
			dt = str(date.fromtimestamp(stat(self.BackupDirectory + config.backupmanager.folderprefix.value + '-' + 'enigma2settingsbackup.tar.gz').st_ctime))
			self.newfilename = self.BackupDirectory + config.backupmanager.folderprefix.value + '-' + dt + '-' + 'enigma2settingsbackup.tar.gz'
			if path.exists(self.newfilename):
				remove(self.newfilename)
			rename(self.BackupDirectory + config.backupmanager.folderprefix.value + '-' + 'enigma2settingsbackup.tar.gz',self.newfilename)
		self.Stage2Complete()

	def Stage2Complete(self):
		self.Stage2Completed = True

	def Stage3(self):
		self.BackupConsole = Console()
		print '[BackupManager] Listing installed plugins'
		self.BackupConsole.ePopen('opkg list-installed', self.Stage3Complete)

	def Stage3Complete(self, result, retval, extra_args):
		print 'result',result
		print 'retval',retval
		print 'extra_args',extra_args
		if retval == 0:
			output = open('/tmp/ExtraInstalledPlugins','w')
			output.write(result)
			output.close()

		if fileExists('/tmp/ExtraInstalledPlugins'):
			print '[BackupManager] Listing completed.'
			self.Stage3Completed = True
		else:
			self.session.open(MessageBox, _("Plugin Listing failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
			print '[BackupManager] Result.',result
			print "{BackupManager] Plugin Listing failed - e. g. wrong backup destination or no space left on backup device"

	def Stage4(self):
		self.BackupConsole = Console()
		tmplist = config.backupmanager.backupdirs.value
		tmplist.append('/tmp/ExtraInstalledPlugins')
		self.backupdirs = ' '.join(tmplist)
		print '[BackupManager] Backup running'
		self.BackupConsole.ePopen('tar -czvf ' + self.BackupDirectory + config.backupmanager.folderprefix.value + '-' + 'enigma2settingsbackup.tar.gz ' + self.backupdirs, self.Stage4Complete)

	def Stage4Complete(self, result, retval, extra_args):
		config.backupmanager.lastlog.setValue(result)
		config.backupmanager.lastlog.save()
		if fileExists(self.BackupDirectory + config.backupmanager.folderprefix.value + '-' + 'enigma2settingsbackup.tar.gz'):
			print '[BackupManager] Complete.'
			remove('/tmp/ExtraInstalledPlugins')
			self.Stage4Completed = True
		else:
			self.session.open(MessageBox, _("Backup failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
			print '[BackupManager] Result.',result
			print "{BackupManager] Backup failed - e. g. wrong backup destination or no space left on backup device"

	def BackupComplete(self):
		if config.backupmanager.schedule.value:
			atLeast = 60
			autoBackupManagerTimer.backupupdate(atLeast)
		else:
			autoBackupManagerTimer.backupstop()
