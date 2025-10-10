#! /usr/bin/env python3

import sys

class Abbreviator:
	class AmbiguousAbbreviation(Exception):
		"Ambiguous abbreviation"

	def __init__(self):
		self._words = set()
		self._abbreviations = {}

	def add(self, word: str):
		self._words.add(word)
		w = word[:-1]
		while w:
			self._abbreviations[w] = None if w in self._abbreviations else word
			w = w[:-1]

	def expand(self, word):
		if word in self._words:
			return word
		w = self._abbreviations[word]
		if w == None:
			raise self.AmbiguousAbbreviation("ambiguous abbreviation")
		return w

class Shell:
	class QuitException(Exception):
		"Quit"

	class IncompleteQuote(Exception):
		"Incomplete quote"

	class ImproperUsage(Exception):
		"Improper usage"

	def __init__(self, stdin = sys.stdin, stdout = sys.stdout):
		self.stdin = stdin
		self.stdout = stdout
		self._abbreviations = Abbreviator()
		self._commands = [] # [dict(command, usage, description)...]
		self._actions = {} # command -> action
		self._aliases = {} # word -> expansion
		self._help_width = 8
		self._alias_width = 1
		self._batch = False
		self.prompt = "> "
		self.prompt2 = ">> "
		self.comment_char = "#"
		self.help_separator = "  - "

	def flush(self):
		self.stdout.flush()

	def writef(self, b):
		self.stdout.write(b)
		self.flush()

	def before_prompt(self, argv):
		pass

	def empty_command(self, argv):
		pass

	def after_command(self, argv):
		pass

	def unknown_command(self, argv):
		self.writef(f'{argv[0]}: Command not found\n')

	def add(self, command, usage, description, action):
		self._commands.append(dict(command=command, usage=usage, description=description))
		self._actions[command] = action
		self._abbreviations.add(command)
		self._help_width = max(self._help_width, len(command) + len(usage) + 1)

	def add_standard_commands(self):
		self.add("alias", "[name [command...]]", "make <name> do <command>, or show aliases", self.do_alias)
		self.add("help", "[command...]", "help on all or specific commands", self.do_help)
		self.add("quit", "", "exit the application", self.do_quit)
		self.add("?", "[command...]", "help on all or specific commands", self.do_help)
		self.add("x", "", "exit the application", self.do_quit)

	def eof(self):
		self.writef("EOF\n")
		raise self.QuitException

	def dispatch(self, argv):
		if argv:
			try:
				try:
					action = self._actions[self._abbreviations.expand(argv[0])]
				except KeyError:
					action = self.unknown_command
				action(argv)
			except self.ImproperUsage:
				self.do_help(['help', argv[0]])
			except Abbreviator.AmbiguousAbbreviation:
				self.writef("Ambiguous abbreviation, please be more specific\n")
				return
		elif not self._batch:
			self.empty_command(argv)

	def dispatch_alias(self, argv):
		alias = self._abbreviations.expand(argv[0])
		self.dispatch(self._aliases[alias] + argv[1:])

	def quote_split(self, s):
		rv = []
		current_word = []
		quoting = None
		whitespace = ' \t\r'
		quotes = '\'"'
		while s:
			c = s[0]
			if c in whitespace:
				if quoting:
					current_word.append(c)
				elif current_word:
					rv.append(''.join(current_word))
					current_word = []
			elif c == '\\':
				current_word.append(s[1:2])
				s = s[1:]
				if s == '\n':
					raise self.IncompleteQuote("\\")
			elif s == '\n':
				if quoting:
					raise self.IncompleteQuote(quoting)
			elif c in quotes:
				if not quoting:
					quoting = c
				elif c == quoting:
					quoting = None
				else:
					current_word.append(c)
			else:
				current_word.append(c)
			s = s[1:]
		if current_word:
			rv.append(''.join(current_word))
		return rv

	def run(self, batch = False):
		saved_batch = self._batch
		self._batch = batch
		argv = []
		while True:
			try:
				if not batch:
					self.before_prompt(argv)
					self.writef(self.prompt)
				line = self.stdin.readline()
				if not line:
					if not batch:
						self.eof()
					return
				elif not line.startswith(self.comment_char):
					while True:
						try:
							argv = self.quote_split(line)
							self.dispatch(argv)
							self.after_command(argv)
							break
						except self.IncompleteQuote:
							if not batch:
								self.writef(self.prompt2)
								line2 = self.stdin.readline()
								if not line2:
									raise EOFError
								line += line2
			except self.QuitException:
				return
			except EOFError:
				self.writef("Unexpected EOF\n")
				return
			except KeyboardInterrupt:
				self.writef("Interrupt\n")
		self._batch = saved_batch

	def readrc(self, filename):
		saved_stdin = self.stdin
		try:
			with open(filename, "r") as f:
				self.stdin = f
				self.run(batch=True)
				return True
		except FileNotFoundError:
			pass
		finally:
			self.stdin = saved_stdin
		return False

	def do_quit(self, argv):
		raise self.QuitException

	def do_help(self, argv):
		commands = []
		for each in argv[1:]:
			try:
				commands.append(self._abbreviations.expand(each))
			except Abbreviator.AmbiguousAbbreviation:
				self.writef(f"{each}: Ambiguous abbreviation, please be more specific\n")
				commands = []
				break
			except KeyError:
				self.writef(f"{each}: Command not found\n")
		fmt = "%%-%ds %%s%%s\n" % (self._help_width, )
		for each in self._commands:
			if len(commands) == 0 or each['command'] in commands:
				self.writef(fmt % (each['command'] + ' ' + each['usage'], self.help_separator, each['description']))

	def do_alias(self, argv):
		if len(argv) > 2:
			alias = argv[1]
			if alias in self._actions and alias not in self._aliases:
				self.writef("You can't override an existing command\n")
				return
			command = self._abbreviations.expand(argv[2])
			if command in self._aliases:
				self.writef("You can't alias an alias\n")
				return
			self._abbreviations.add(alias)
			self._actions[alias] = self.dispatch_alias
			self._aliases[alias] = [command] + argv[3:]
			self._alias_width = max(self._alias_width, len(alias))
		else:
			alias = None
			alias_expansion = []
			if len(argv) == 2:
				try:
					alias = self._abbreviations.expand(argv[1])
					alias_expansion = self._aliases[alias]
				except KeyError:
					self.writef("Unknown alias\n")
					return
				except Abbreviator.AmbiguousAbbreviation:
					self.writef("Ambiguous alias abbreviation, please be more specific\n")
					return
			fmt = "alias %%-%ds  %%s\n" % (self._alias_width, )
			for k, v in ([(alias, alias_expansion)] if alias else self._aliases.items()):
				self.writef(fmt % (k, ' '.join(v)))

# if __name__ == "__main__":
if True:
	import os

	def foo(argv):
		print("foo", argv)

	class TestShell(Shell):
		def __init__(self, *s, **kw):
			Shell.__init__(self, *s, **kw)
			self._history_number = 1

		def before_prompt(self, argv):
			self.prompt = f'TestShell {self._history_number} > '

		def after_command(self, argv):
			if argv and not self._batch:
				self._history_number += 1

	s = TestShell()
	s.add("foo", "[something [...]]", "does some stuff", foo)
	s.add("fo", "[something [...]]", "does some stuff", foo)
	s.add_standard_commands()
	s.readrc(os.path.expanduser("~/.appshellrc"))
	s.run()
