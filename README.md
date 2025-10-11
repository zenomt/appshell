Python Line-Oriented Command Interpreter
========================================
This module provides the `appshell.Shell` class, which is a simple line-oriented
command interpreter similar to Python's built-in `cmd.Cmd` class, but providing
ergonomic alternatives that the author prefers.

In particular, the user can abbreviate commands (as long as the abbreviation isn't
ambiguous), and the shell supports simple user-created command aliases.

_`class`_ `appshell.Shell(stdin=sys.stdin, stdout=sys.stdout)`
--------------------------------------------------------------
An instance of `Shell` (or a subclass) is a line-oriented command interpreter.
You add commands for it to recognize with `Shell.add_command()`, optionally
add the standard command suite (`help`, `quit`, and `alias`), and start it
running. It reads lines from its input (default `sys.stdin`), each line
representing one command. The first word on the line is the name of the
command, and the remaining words (if any) are the command's command-specific
arguments.  It runs until its input is exhausted or `Shell.QuitException` is
raised (this is what the `quit` command does).

Lines beginning with the comment character (`#` by default) are ignored.

Words are separated by ASCII whitespace (spaces and tabs), unless quoted.
Both single-quote `'` and double-quote `"` can be used to quote words with
spaces (or the other kind of quote) in them. Any character, including whitespace
or a quote, can be escaped with a backslash `\`. The escaping may be enhanced
in the future to enable common string escapes (like `\n` for newline).

The user can define an alias for a command, including initial arguments.  When
an alias is given, it is expanded to the original command and initial arguments,
with following arguments appended. For example

    alias bar foo baz

means that if the user enters `bar biff`, it should be interpreted as though
`foo baz biff` was entered.

`Shell` Objects
---------------

Instance variables:

* `Shell.stdin` - File object from which commands are read with its `readline()` method; `sys.stdin` by default.
* `Shell.stdout` - File object to which output is written; `sys.stdout` by default.
* `Shell.help_width` - The width, in characters, for command names and usages in the `help` so that
  the help summaries will all be aligned. This starts at 8 characters and is extended as commands are added.
* `Shell.alias_width` - The width, in characters, for the word `alias` and the alias name,
  so that expansions will be aligned when listing aliases; 1 by default.
* `Shell.prompt` - The prompt to display before the next command is read, default "`> `".
* `Shell.prompt2` - The prompt to display to continue a line if the previous line ended mid-quote, default "`>> `".
* `Shell.comment_char` - The character or string that, if a line begins with it, the line is ignored, default "`#`".
* `Shell.help_separator` - The string to separate a command name and usage from its summary in `help`, default "`  - `".

Instance methods:

* `Shell.add_command(*, action, name=None, usage='', summary='', help='')` <br>
  Add a new command to the be recognized by the shell. Parameters:
  - `action` - A callable to call to execute the command, which takes one argument: a list
    of the argument vector for the command, including the command's name as entered.
  - `name` - The name for the command; if not specified, the name is the action's `__name__`
    minus a leading `do_`, if any.
  - `usage` - An optional short string for the help to indicate options or arguments the command might take.
  - `summary` - A short summary of the command to display in the help after the `help_separator`;
    if not specified, it is the summary line from the action's docstring, if any.
  - `help` - If specified, the "long help" to display if help is requested for this command specifically;
    if not specified, it is the rest of the action's docstring after the summary, if any.
* `Shell.add(*, name=None, usage='', summary='', help='')` <br>
  Convenience decorator to call `add_command()` with the decorated function as the action.
  Returns the action callable with no additional wrapping.
* `Shell.add_standard_commands()` <br>
  Add the suite of standard commands and their alternate names; specifically `alias`,
  `help`, `quit`, `?` (the same as `help`), and `x` (the same as `quit`).
* `Shell.run(batch=False)` <br>
  Run the command interpreter, reading lines with `Shell.stdin.readline()` until the end of
  the input is reached, or `Shell.QuitException` is raised. If `batch` is `True`, don't print
  the prompt before reading each command.
* `Shell.readrc(filename)` <br>
  Attempt to read commands from the file named `filename` by opening it and temporarily setting `Shell.stdin` to
  the file and executing `Shell.run(batch=True)`.
* `Shell.do_quit(argv)` <br>
  Raise `Shell.QuitException` to quit the application.
* `Shell.do_help(argv)` <br>
  - With no arguments, prints the summary help for all commands.
  - With exactly one argument, prints the summary and long help (if any) for that command.
  - With more than one argument, prints the summary help for the indicated commands.
* `Shell.do_alias(argv)` <br>
  - With no arguments, show all aliases.
  - With one argument, show the expansion for just that alias.
  - With more than one argument, define an alias named by the first argument that expands to the remaining arguments.
* `Shell.before_prompt(argv)` <br>
  Called just before printing the prompt; `argv` is the argument vector from the previous command.
  The default implementation does nothing.
* `Shell.after_command(argv)` <br>
  Called after invoking the action for a command; `argv` is the argument vector from the command just invoked.
  The default implementation does nothing.
* `Shell.empty_command(argv)` <br>
  If not in `batch` mode, called if the user enters a blank line. The default implementation does nothing.
* `Shell.write(b)` <br>
  Convenience method writes `b` to `Shell.stdout`.
* `Shell.writef(b)` <br>
  Convenience method writes `b` to `Shell.stdout` then calls `Shell.flush()`.
* `Shell.flush()` <br>
  Convenience method calls `Shell.stdout.flush()`.

Exceptions:

* `Shell.QuitException` <br>
  Raise this in an action to terminate `Shell.run()`.
* `Shell.ImproperUsage` <br>
  Convenience: raise this in an action to print the help message for the invoked command.

Example
-------

    from appshell.appshell import Shell

    shell = Shell()

    @shell.add(usage="[args...]")
    def do_foo(argv):
        """
        Print my argument vector

        Long help for this command.
        """
        print(argv)

    shell.add_standard_commands()

    if __name__ == "__main__":
        shell.run()

The above example adds one command `foo`, with a help usage string of
"`[args...]`", a help summary of "`Print my argument vector`", and long help.
It then adds the standard command suite and then runs the command interpreter.
A sample run might look like:

    $ python3 example.py
    > h
    foo [args...]               - Print my argument vector
    alias [name [command...]]   - make <name> do <command>, or show aliases
    help [command...]           - help on all or specific commands
    quit                        - exit the application
    ? [command...]              - help on all or specific commands
    x                           - exit the application
    > help f
    foo [args...]               - Print my argument vector
    ===
    Long help for this command.
    > f one two "three four"
    ['f', 'one', 'two', 'three four']
    > alias bar foo bar
    > bar baz
    ['foo', 'bar', 'baz']
    > quit
    $
