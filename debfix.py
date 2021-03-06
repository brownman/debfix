#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function
from argparse import ArgumentParser
import subprocess
import logging
import os
import re

data_dir = 'debfix/'  # where files are, except dot-files
log = logging.getLogger()
assume_yes = False

def _init_logging():
  log.setLevel(logging.DEBUG)
  ch = logging.StreamHandler()
  ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
  log.addHandler(ch)

def user_choice(question, other_choices=''):
  """Get user's response y/N/q to question.
  Returns True (Y), False (N), (Q)uit, or any other char from other_choices."""
  print('----------------------------------------------')
  choice = '("" in "ynq") resolves to True, so choice must be non-blank'
  question = '{} ? (y/N/q{}): '.format(question, '/'+'/'.join(other_choices) if other_choices else '')
  valid_choices = 'ynq' + other_choices
  while choice not in valid_choices:
    choice = 'y' if assume_yes else (raw_input(question).lower() or 'n')
    if   choice == 'y': return True
    elif choice == 'n': return False
    elif choice == 'q': os.sys.exit(0)
    elif choice in other_choices: return choice

def run(cmd, pipe=False):
  """Executes cmd string and returns True on success or stdout if pipe=True"""
  if pipe:
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
  return 0 == subprocess.call(cmd, shell=True)

"""Function beginning with 'do_' are the action functions that perform
changes. Their __doc__ is the 'question' for the user_choice()."""

def do_0_copy_apt_config_no_triggers():
  """Optimize performance of apt by defering DPkg triggers"""
  if run('cp -v {}etc_apt_apt.conf.d_99defer-triggers /etc/apt/apt.conf.d/99defer-triggers'.format(data_dir)):
    log.info('Created /etc/apt/apt.conf.d/99defer-triggers')
  else:
    log.warn('Failed to copy 99defer-triggers to /etc/apt/apt.conf.d')

def do_0_copy_debian_sources_list():
  """Set 'perfect' Debian-ONLY /etc/apt/sources.list"""
  release = 'wheezy'
  if not assume_yes:
    release = raw_input('Debian release to track (stable/sid/...) [{}]: '
                        .format(release)).lower() or release
  cmd = ('mv -v /etc/apt/sources.list /etc/apt/sources.list~debfix '
         '&& cp -v {path}etc_apt_sources.list /etc/apt/sources.list '
         '&& echo "deb http://www.deb-multimedia.org {rel} main non-free" >> /etc/apt/sources.list.d/deb-multimedia.list'
         '&& sed -i "s/wheezy/{rel}/g" /etc/apt/sources.list'.format(path=data_dir, rel=release))
  if run(cmd):
    log.info('Created /etc/apt/sources.list (old backed-up as sources.list~debfix) and /etc/apt/sources.list.d/deb-multimedia.list')
  else:
    log.warn('Failed to create /etc/apt/sources.list and /etc/apt/sources.list.d/deb-multimedia.list. Please DO investigate manually!')

def do_copy_synaptic_config():
  """Create friendly Synaptic (package manager) settings"""
  if run('[ ! -d /root/.synaptic ] && mkdir -v /root/.synaptic ; '
          '[ -f /root/.synaptic/synaptic.conf ] && mv -v /root/.synaptic/synaptic.conf /root/.synaptic/synaptic.conf~ ; '
          'cp {}root_.synaptic_synaptic.conf /root/.synaptic/synaptic.conf'.format(data_dir)):
    log.info('Created /root/.synaptic/synaptic.conf')
  else:
    log.warn('Failed to move root_.synaptic_synaptic.conf to /root/.synaptic/synaptic.conf')

def do_20_copy_xorg_synaptics_config():
  """Set touchpad tap-to-click and edge scrolling"""
  if run('[ ! -d /etc/X11/xorg.conf.d ] && mkdir -v /etc/X11/xorg.conf.d ; '
         'cp -v {}etc_X11_xorg.conf.d_50-synaptics.conf /etc/X11/xorg.conf.d/50-synaptics.conf'.format(data_dir)):
    log.info('Created /etc/X11/xorg.conf.d/50-synaptics.conf')
  else:
    log.warn('Failed to copy 50-synaptics.conf to /etc/X11/xorg.conf.d')

def do_20_ensure_sudo_mode():
  """If you use sudo, gksu may fail when running update-manager,
unetbootin etc. from the menu (see bug http://bugs.debian.org/481689).
gksu only fails if root user is without password (passwd -d root) or
locked and if GConf key /apps/gksu/sudo-mode is not set.
Ensure sudo-mode is set"""
  if run('if passwd -S root | grep -E "NP|L" >/dev/null 2>&1; then '
            'update-alternatives --set libgksu-gconf-defaults /usr/share/libgksu/debian/gconf-defaults.libgksu-sudo '
            '&& update-gconf-defaults ; '
         'fi'):
    log.info('sudo-mode set via libgksu-gconf-defaults alternatives')
  else:
    log.warn('Failed to update-alternatives for libgksu-gconf-defaults')

def do_20_disable_sudoers_tty_tickets():
  """Using sudo, you were supposed to only type the password in once every
15 minutes. Unfortunately, each tty/pts session creates a separate
timestamp which means that in practice you are asked to retype your
password far more often. If this bugs you, you can set a global per-user
(instead of per tty session) timestamp ticket file.
Disable tty_tickets in /etc/sudoers"""
  if run("echo '\nDefaults\tinsults,!tty_tickets\n' >> /etc/sudoers"):
    log.info("'Defaults insults,!tty_tickets' line added to /etc/sudoers")
  else:
    log.warn('Failed to disable tty_tickets. Hope your sudoers file is not broken. :-|')

def do_20_add_user_to_fuse_group():
  """FUSE (Filesystem in Userspace) requires the mounting user to be in
fuse group. If anticipate to need fuse (or not), add user to fuse group"""
  user = run("echo $(cat /etc/passwd | grep ':1000:' | cut -d ':' -f 1 )", pipe=True).strip()
  if not assume_yes:
    user = raw_input('User to add to fuse group (by default, user with gid 1000) [{}]: '
                     .format(user)) or user
  if run('adduser {} fuse'.format(user)):
    log.info("User '{}' added to group 'fuse'".format(user))
  else:
    log.warn("Failed to add {} to 'fuse' group. Is fuse installed?".format(user))  

def do_set_noatime_in_fstab_mounts():
  """Filesystems may make **SEVERAL DIRK WRITES FOR EACH READ** operation
as they update the access times of files and their parent directories!
Setting 'noatime' flag on mount points may thus increase disk performace.
Set 'noatime' flag on all non-tmpfs mounts defined in /etc/fstab"""
  newfstab = []
  with open('/etc/fstab') as fstab:
    for line in fstab:
      match = re.search('^([^#\s]+)\s+([^#\s]+)\s+([^#\s]+)\s+([^#\s]+)\s+([0-9]+)\s+([0-9]+[.]*)', line, re.DOTALL)
      if not match:  # no match, so a comment line
        newfstab.append(line)
        continue
      line = list(match.groups())
      if line[0] != 'tmpfs' and 'noatime' not in line[3]:
        line[3] += ',noatime'
      newfstab.append('\t'.join(line) + '\n')
  with open('/etc/fstab', 'w') as fstab:
    fstab.write(''.join(newfstab) + '\n')
  log.info("'noatime' flag added to non-tmpfs mounts in /etc/fstab")

def do_add_tmpfs_mount_to_fstab():
  """Firefox may store partly downloaded files/YouTube videos to /tmp.
As a result, /tmp can sometimes grow quite large, well over 800M default.
Add 'tmpfs /tmp ...size=2G...' to /etc/fstab"""
  if run('echo "\ntmpfs /tmp tmpfs nodev,nosuid,size=2G,mode=1777 0 0" >> /etc/fstab'):
    log.info('tmpfs line added to /etc/fstab.')
  else:
    log.warn('Failed to add tmpfs line to /etc/fstab')

def do_add_usbfs_mount_to_fstab():
  """VirtualBox (and VMWare, etc.) may need the following line in /etc/fstab:
usbfs /proc/bus/usb usbfs busgid=1000,busmode=0775,devgid=1000,devmode=0664 0 0
Add above line to /etc/fstab"""
  if run('echo "\nusbfs /proc/bus/usb usbfs busgid=1000,busmode=0775,devgid=1000,devmode=0664 0 0" >> /etc/fstab'):
    log.info('usbfs line added to /etc/fstab.')
  else:
    log.warn('Failed to add usbfs line to /etc/fstab')

def do_fix_initramfs_hibernate_resume():
  """The value in /etc/initramfs-tools/conf.d/resume must match the UUID of
the swap partition (from /etc/fstab, or result of `blkid`) in order for resume
from hibernation to work.
Ensure UUIDs match"""
  with open('/etc/fstab') as fstab:
    try: uuid = re.search('^([^#\s]+)\s+[^#\s]+\s+swap\s+[^#\s]+\s+[0-9]+\s+[0-9]+', fstab.read(), re.MULTILINE).groups()[0]
    except (AttributeError, IndexError): uuid = ''
  cmd = ('echo "RESUME=' + uuid + '" > /etc/initramfs-tools/conf.d/resume '
         '&& update-initramfs -u -k all')
  if uuid and run(cmd):
    log.info('/etc/initramfs-tools/conf.d/resume set to ' + uuid)
  else:
    log.warn('Failed to set /etc/initramfs-tools/conf.d/resume to "{}"'.format(uuid))

def do_disable_pc_speaker():
  """Disable annoying PC-speaker (bell)"""
  if run('echo "blacklist pcspkr" >> /etc/modprobe.d/blacklist.conf'):
    log.info('pcspkr blacklisted in /etc/modprobe.d/blacklist.conf')
  else:
    log.warn('Failed to blacklist pcspkr module')

def do_improve_desktop_system_performance():
  """Improve desktop system performance by various kernel (sysctl) tweaks"""
  echo_sampling_down_factor = (
      '[ -f /sys/devices/system/cpu/cpufreq/ondemand/sampling_down_factor ] '
      '&& echo 1000 > /sys/devices/system/cpu/cpufreq/ondemand/sampling_down_factor'
  )
  try:  # add script to /etc/rc.local
    with open('/etc/rc.local') as f: rclines = f.readlines()
    inserted = False
    for i, line in enumerate(rclines):
      if not line.startswith('#'):
        rclines.insert(i, echo_sampling_down_factor)
        inserted = True
        break
    if not inserted: rclines.append(echo_sampling_down_factor)
    with open('/etc/rc.local', 'w') as f: f.write('\n'.join(rclines))
    log.info('Tuned sampling_down_factor in /etc/rc.local')
  except IOError: pass
  # add upstart rule
  if run('cp -v {}etc_init_sampling-down-factor.conf /etc/init/sampling-down-factor.conf '
         '&& chmod u+x /etc/init/sampling-down-factor.conf'.format(data_dir)):
    log.info('Tuned sampling_down_factor by upstart rule in /etc/init/sampling-down-factor.conf')
  # sysctl optimizations
  if run('cp -v {}etc_sysctl.d_debfix-desktop-performance.conf /etc/sysctl.d/debfix-desktop-performance.conf'.format(data_dir)):
    log.info('Created /etc/sysctl.d/debfix-desktop-performance.conf')
  else:
    log.warn('Failed to create /etc/sysctl.d/debfix-desktop-performance.conf')

def _apt_install_packages(marked, second_time_around=False):
  # PRE
  if 'mozilla' in marked['sections'] and not second_time_around:
    run('[ ! -d /etc/apt/sources.list.d ] && mkdir /etc/apt/sources.list.d ; '
        'cp -v {}etc_apt_sources.list.d_experimental-iceweasel-esr.list /etc/apt/sources.list.d/experimental-iceweasel-esr.list'.format(data_dir))
    run('apt-get -q update')
    run('apt-get -y -q --allow-unauthenticated install pkg-mozilla-archive-keyring')
    run('[ ! -d /etc/apt/preferences.d ] && mkdir /etc/apt/preferences.d ; '
        'cp -v {}etc_apt_preferences.d_experimental-iceweasel-esr.pref /etc/apt/preferences.d/experimental-iceweasel-esr.pref'.format(data_dir))
    run('apt-get -q update')
  # INSTALL
  if marked['install']: run('aptitude -y -q install ' + marked['install'])
  # REMOVE
  if marked['remove']: run('aptitude -y -q purge ' + marked['remove'])
  # POST
  if 'virtualbox' in marked['sections']:
    try:
      # this regex fails until vboxdrv is properly installed
      version = re.search('^[0-9]+\.[0-9]+\.[0-9]+', run('VBoxManage -v', pipe=True).split('\n')[-2]).group()
      run('cd /tmp '
          '&& wget http://download.virtualbox.org/virtualbox/{version}/Oracle_VM_VirtualBox_Extension_Pack-{version}.vbox-extpack '
          '&& VBoxManage extpack install /tmp/Oracle_VM_VirtualBox_Extension_Pack-{version}.vbox-extpack'.format(version=version))
    except AttributeError:
      log.warn('VBox extension pack failed to install. Please install it manually.')
      

def do_10_install_packages():
  """Install or remove packages (as per debfix/debfix-packages.conf"""
  from ConfigParser import RawConfigParser
  config = RawConfigParser(allow_no_value=True)
  config.read(data_dir + 'debfix-packages.conf')
  sections = config.sections()
  run('apt-get -y -q update')
  run('apt-get -y -q --allow-unauthenticated install aptitude debian-archive-keyring deb-multimedia-keyring')
  run('apt-get -y -q update')
  if user_choice('Upgrade all upgradable packages'):
    run('aptitude -y -q full-upgrade')
  marked = {'install':'', 'remove':'', 'sections':''}
  for section in sections:
    question = "{} packages from '{}' section".format('Install' if section != 'remove' else 'Remove', section)
    packages = ' '.join(i[0] for i in config.items(section))
    while True:
      choice = user_choice(question, other_choices='?')
      if choice == '?':
        log.info("Section '{}' contains packages: {}".format(section, packages))
        continue
      if choice:
        marked['sections'] += section + ' '
        if section == 'remove':
          marked['remove'] += packages + ' '
        else:
          marked['install'] += packages + ' '
      break
  if user_choice('Install: {install}\nRemove: {remove}\nApply changes'.format(**marked)):
    _apt_install_packages(marked)
    # due to assume-yes-based decisions, some packages may not be successfully installed (yet), retry
    _apt_install_packages(marked, second_time_around=True)
  run('aptitude -y -q clean')
  log.info('Done installing packages')

def do_install_teamviewer():
  """Install TeamViewer (remote support software)"""
  arch = '_x64' if int(run('getconf LONG_BIT', pipe=True)) == 64 else ''
  if run('cd /tmp '   # TODO: please recommend how to avoid 'symlink attack' vector in the lines below
         '&& wget -O teamviewer_linux.deb http://www.teamviewer.com/download/teamviewer_linux{}.deb'
         '&& gdebi -n -q teamviewer_linux.deb'.format(arch)):
    log.info('TeamViewer installed')
  else:
    log.warn('Failed to install TeamViewer')

def do_install_skype():
  """Install Skype"""
  if run('cd /tmp '   # TODO: see teamviewer TODO
         '&& wget -O skype_linux.deb http://www.skype.com/go/getskype-linux-deb-32'
         '&& gdebi -n -q skype_linux.deb'):
    log.info('Skype installed')
  else:
    log.warn('Failed to install Skype')

def main():
  if os.getuid() != 0:
    print('This script should be run as root.')
    exit()
  
  parser = ArgumentParser(description="Fix (and optimize) Debian with an interactive script that helps you set up your mom's PC.",
                          epilog='Source: http://github.com/kernc/debfix',
                          prog='./debfix.py')
  parser.add_argument('-y', '--assume-yes', action='store_true',
                     help='assume "yes" as answer to all prompts')
  global assume_yes
  assume_yes = parser.parse_args().assume_yes
  
  _init_logging()
  for fname, func in sorted(globals().items()):
    if fname.startswith('do_') and user_choice(func.__doc__):
      func()
  print('All done.')

if __name__ == '__main__':
  main()
