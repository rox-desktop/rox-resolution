import os, popen2, sys
import rox

paths = os.environ.get('PATH', '/bin:/usr/bin').split(':')
paths += ['/sbin', '/usr/sbin', '/usr/local/sbin']
for p in paths:
	xrandr = os.path.join(p, 'xrandr')
	if os.access(xrandr, os.X_OK):
		break
else:
	raise Exception(
		_('The xrandr command is not installed. I looked in all '
		  'these directories:\n\n- ' + '\n- '.join(paths) + '\n\n'
		  "This probably means that resizing isn't supported on your "
		  'system. Try upgrading your X server.'))

class Setting:
	def __init__(self, line):
		bits = [b for b in line.split() if b]
		self.n = int(bits[0])
		self.width = int(bits[1])
		self.height = int(bits[3])
		self.phy_width = bits[5]
		self.phy_height = bits[7]
		self.res = []
		self.current_r = None
		for r in bits[9:]:
			if r.startswith('*'):
				self.current_r = int(r[1:])
				self.res.append(self.current_r)
			else:
				self.res.append(int(r))
	
	def __str__(self):
		return '%s x %s' % (self.width, self.height)

class NewSetting(Setting):
	def __init__(self, line, phy_width, phy_height):
		bits = [b for b in line.split() if b]
		self.n = -1
		self.width, self.height = bits[0].split('x')
		self.width = int(self.width)
		self.height = int(self.height)
		self.phy_width = phy_width
		self.phy_height = phy_height
		self.res = []
		self.current_r = None
		for r in bits[1:]:
			res = float(r.strip('*+'))
			if r.endswith('*'):
				self.current_r = res
			self.res.append(res)
	
def get_settings():
	cout, cin = popen2.popen2([xrandr])
	cin.close()
	settings = []
	current = None
	phy_width = 0
	phy_height = 0
	for line in cout:
		line = line.rstrip()
		if 'mm x ' in line and line.endswith('mm'):
			data = line.rsplit(' ', 3)
			if data[1].endswith('mm') and data[3].endswith('mm'):
				phy_width = data[1]
				phy_height = data[3]
		elif line[0] in ' *' and 'x' in line:
			try:
				if ' x ' in line:
					setting = Setting(line[1:])
				else:
					setting = NewSetting(line, phy_width, phy_height)
				settings.append(setting)
				if '*' in line:
					current = setting
			except Exception, ex:
				print >>sys.stderr, "Failed to parse line '%s':\n%s" % \
					(line.strip(), str(ex))
	cout.close()
	return (current, settings)

def set_mode(setting):
	cerr, cin = popen2.popen4([xrandr, '-s', '%dx%d' %
		(setting.width, setting.height)])
	cin.close()
	errors = cerr.read()
	if errors:
		rox.alert(_("Errors from xrandr: '%s'") % errors)
