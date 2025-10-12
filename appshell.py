#! /usr/bin/env python3

# Copyright © 2025 Michael Thornburgh
# SPDX-License-Identifier: MIT

import sys
import pydoc

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
	class _IncompleteQuote(Exception):
		"Incomplete quote"

	class Quit(Exception):
		"Quit"

	class ImproperUsage(Exception):
		"Improper usage"

	def __init__(self, stdin=None, stdout=sys.stdout):
		self._abbreviations = Abbreviator()
		self._commands = [] # [dict(name, usage, summary, help)...]
		self._actions = {} # name -> action
		self._aliases = {} # alias -> expansion
		self._batch = False
		self.stdin = stdin
		self.stdout = stdout
		self.help_width = 8
		self.alias_width = 1
		self.prompt = "> "
		self.prompt2 = ">> "
		self.comment_char = "#"
		self.help_separator = "  - "

	def input(self, prompt):
		if self.stdin:
			if not self._batch:
				self.writef(prompt)
			return self.stdin.readline()
		try:
			rv = input('' if self._batch else prompt)
			return rv if rv.endswith('\n') else rv + '\n'
		except EOFError:
			return ''

	def write(self, b):
		self.stdout.write(b)

	def flush(self):
		self.stdout.flush()

	def writef(self, b):
		self.write(b)
		self.flush()

	def before_prompt(self, argv):
		pass

	def empty_command(self, argv):
		pass

	def after_command(self, argv):
		pass

	def unknown_command(self, argv):
		self.writef(f'{argv[0]}: Command not found\n')

	def add_command(self, *, action, name=None, usage="", summary="", help=""):
		name = name or (action.__name__[3:] if action.__name__.startswith("do_") else action.__name__)
		doc_summary, long_help = pydoc.splitdoc(pydoc.getdoc(action))
		summary = summary or doc_summary
		help = help or long_help
		self._commands.append(dict(name=name, usage=usage, summary=summary, help=help))
		self._actions[name] = action
		self._abbreviations.add(name)
		self.help_width = max(self.help_width, len(name) + len(usage) + 1)

	def add(self, *, name=None, usage="", summary="", help=""):
		"""Convenience decorator to add a command for the decorated function."""
		def register_command(func):
			self.add_command(action=func, name=name, usage=usage, summary=summary, help=help)
			return func
		return register_command

	def add_standard_commands(self):
		self.add_command(action=self.do_alias, usage="[name [command...]]")
		self.add_command(action=self.do_help, usage="[command...]")
		self.add_command(action=self.do_quit)
		self.add_command(action=self.do_help, name="?", usage="[command...]")
		self.add_command(action=self.do_quit, name="x")

	def eof(self):
		self.writef("EOF\n")
		raise self.Quit

	def dispatch(self, argv):
		if argv:
			try:
				try:
					action = self._actions[self._abbreviations.expand(argv[0])]
				except KeyError:
					action = self.unknown_command
				action(argv)
			except self.ImproperUsage:
				self.write("Improper usage.\n")
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
					raise self._IncompleteQuote("\\")
			elif s == '\n':
				if quoting:
					raise self._IncompleteQuote(quoting)
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
				line = self.input(self.prompt)
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
						except self._IncompleteQuote:
							line2 = self.input(self.prompt2)
							if not line2:
								raise EOFError
							line += line2
			except self.Quit:
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
		"""exit the application"""
		raise self.Quit

	def do_help(self, argv):
		"""help on all or specific commands"""

		commands = set()
		for each in argv[1:]:
			try:
				commands.add(self._abbreviations.expand(each))
			except Abbreviator.AmbiguousAbbreviation:
				self.write(f"{each}: Ambiguous abbreviation, please be more specific\n")
				commands = set()
				break
			except KeyError:
				self.write(f"{each}: Command not found\n")
		fmt = "%%-%ds %%s%%s\n" % (self.help_width, )
		for each in self._commands:
			if len(commands) == 0 or each['name'] in commands:
				self.write(fmt % (each['name'] + ' ' + each['usage'], self.help_separator, each['summary']))
				if len(commands) == 1 and each['help']:
					self.write("===\n")
					self.write(each['help'])
					self.writef("\n")
		self.flush()

	def do_alias(self, argv):
		"""
		make <name> do <command>, or show aliases

		With no arguments, show all aliases.
		With one argument, show just that alias.
		With two or more arguments, define an alias of <name> to do <command>.
		"""

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
			self.alias_width = max(self.alias_width, len(alias))
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
			fmt = "alias %%-%ds  %%s\n" % (self.alias_width, )
			for k, v in ([(alias, alias_expansion)] if alias else self._aliases.items()):
				self.write(fmt % (k, ' '.join(v)))
			self.flush()

if __name__ == "__main__":
	import os
	import readline

	class TestShell(Shell):
		def __init__(self, *s, **kw):
			Shell.__init__(self, *s, **kw)
			self._history_number = 1

		def before_prompt(self, argv):
			self.prompt = f'TestShell {self._history_number} > '

		def after_command(self, argv):
			if argv and not self._batch:
				self._history_number += 1

	shell = TestShell()

	@shell.add(name="fo", usage="[something [...]]", summary="does a thing")
	@shell.add(usage="[something [...]]")
	def do_foo(argv):
		"""does something"""
		print("foo", argv)

	@shell.add(summary="something else. i have long help.")
	def do_other(argv):
		"""
		This docstring should just be the long help because there's
		no blank line after the first line. Calling me raises
		Shell.ImproperUsage, which should say so.
		"""
		raise Shell.ImproperUsage

	shell.add_standard_commands()
	shell.readrc(os.path.expanduser("~/.appshellrc"))
	shell.run(batch = not sys.stdin.isatty())
