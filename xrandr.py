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
		self.n = -1
		self.width, self.height = bits[0].split('x')
		self.width = int(self.width)
		self.height = int(self.height)
		self.res = []
		self.current_r = None
		self.preferred_r = None
		for r in bits[1:]:
			try:
				res = float(r.strip('*+'))
			except ValueError:
				continue
			if '*' in r:
				self.current_r = res
			if '+' in r:
				self.preferred_r = res
			self.res.append(res)
	
	def __str__(self):
		return '%s x %s' % (self.width, self.height)

class Settings(list):

	def __init__(self, output_index, output, phy_width, phy_height):
		self.output = output
		self.output_index = output_index
		self.phy_width = phy_width
		self.phy_height = phy_height
		self.current = None
		self.preferred = None
		self.enabled = self.phy_width != 0
		self.direction = 'same-as'
		self.other_output = None

def get_settings(xrandr_args):
	cout, cin = popen2.popen2([xrandr])
	cin.close()
	settings = {}
	output = ''
	i = 0
	for line in cout:
		line = line.rstrip()
		if 'connected' in line:
			if 'disconnected' in line:
				continue
			phy_width = 0
			phy_height = 0
			if 'mm x ' in line and line.endswith('mm'):
				data = line.rsplit(' ', 3)
				if data[1].endswith('mm') and data[3].endswith('mm'):
					phy_width = data[1]
					phy_height = data[3]
			output = line.split(' ')[0]
			settings[output] = Settings(i, output, phy_width, phy_height)
			i += 1
		elif line[0] in ' *' and 'x' in line:
			try:
				setting = Setting(line)
				settings[output].append(setting)
				if '*' in line:
					settings[output].current = setting
				if '+' in line:
					settings[output].preferred = setting
			except Exception, ex:
				print >>sys.stderr, "Failed to parse line '%s':\n%s" % \
					(line.strip(), str(ex))
	cout.close()

	it = iter(xrandr_args.split(' '))

	output = ''
	while True:
		try:
			arg = it.next()
		except StopIteration:
			break
		if arg == '--output':
			try:
				output = it.next()
			except StopIteration:
				# Invalid args: --output not followed by output name.
				break
		elif arg in {'--same-as', '--left-of', '--right-of', '--above', '--below'}:
			try:
				output_settings = settings[output]
			except KeyError:
				# Configured output not connected.
				continue
			output_settings.direction = arg[2:]
			try:
				output_settings.other_output = it.next()
			except StopIteration:
				# Invalid args: direction not followed by output name.
				break
		elif arg == '--mode':
			try:
				width, height = [int(s) for s in it.next().split('x')]
			except (StopIteration, ValueError):
				# Invalid args: --mode not followed by valid mode string.
				break
			else:
				for setting in settings[output]:
					if setting.width == width and setting.height == height:
						settings[output].current = setting
						break
		elif arg == '--rate':
			# This code relies on --mode being set before --rate,
			# so settings[output].current is set to the setting currently
			# saved.
			try:
				rate = float(it.next())
			except (StopIteration, ValueError):
				# Invalid args: --rate not followed by valid rate string.
				break
			else:
				try:
					settings[output].current.current_r = rate
				except (KeyError, AttributeError):
					# Output disabled.
					continue
	return settings

def settings_to_args(output2settings):
	args = []
	for output, settings in output2settings.iteritems():
		args += ['--output', output]
		current = settings.current
		if settings.enabled:
			args += ['--mode', '%dx%d' % (current.width, current.height)]
		else:
			args.append('--off')
		if current.current_r is not None:
			args += ['--rate', str(current.current_r)]
		if settings.other_output is not None:
			args += ['--%s' % settings.direction, settings.other_output]
	return args

def set_modes(output2settings):
	cmd = [xrandr] + settings_to_args(output2settings)
	cerr, cin = popen2.popen4(cmd)
	cin.close()
	errors = cerr.read()
	if errors:
		rox.alert(_("Errors from xrandr: '%s'") % errors)
