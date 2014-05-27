---
layout: default
title: What's new in DreamPie
---

What's new in the Git Repo
-----------------------

* Added an alternative icon by Rafael Bachmann to the misc/ directory. Thanks!
* Fix bug reported by Bo Bayles: In Python 3.3 the site-packages directory
  wasn't added to sys.path.

What's new in DreamPie 1.2.1
-------------------------

DreamPie 1.2.1 was released on 2012/10/18.

* Now using the keypad enter key always executed - now you don't have to press
  Ctrl-Enter any more!
* Fix a bug: the code typed wasn't highlighted when using the released version
  (Thanks Bo Bayles!)
* Fix bug lp:1051742: sporadic AssertionErrors about is_executing (Thanks Brendan!)

What's new in DreamPie 1.2
--------------------------

DreamPie 1.2 was released on 2012/09/25. Quite a lot has improved about DreamPie
in the last two years, but I was too lazy to make a release. So here it comes!
These are a few highlights:

* Fix the horrible GTK crash when mouse goes over updating folded text!
* In order to make development more dynamic, DreamPie has moved to GitHub, and
  now it's much easier to run from a repository. It will also let you know if
  a new release or a new git commit is available.
* Mac support: Now you can install PyGTK and it will Just Work!
* Now you can press ctrl-T and open a new tab for code. This is useful if you
  started writing something, and then remembered that you need to import
  something before it may work. Just press Ctrl-T, run the import, and press
  Ctrl-W to close the temporary tab.
* Indent and dedent a block of code by selecting it and pressing Tab/Shift-Tab.
* Ctrl-Up and Ctrl-Down don't bring the same code twice.
* Dictionary key completion.
* Move to the beginning of the line by pressing 'Home' twice.
* Pressing Enter on an executed code now appends instead of replaces the
  current code. You can select multiple commands and they all will be copied.
* Improved behavior when running GUI code when idle - now Ctrl-C stops it,
  and using completion will not hung DreamPie.
* Now the code box doesn't start collapsed when using Ubuntu's overlay
  scrollbars.
* Highlight matching brackets with four different colors. Also, highlight
  bracketing errors.
* Re-open completion list after backspace is pressed.
* Undo autoparens when user continues typing something that doesn't make
  sense with parens.
* Set 'exit' and 'quit' objects to help users. Previously they were misleading.
* Add a "--run" command line option, to run a file once.
* Add an option for a vertical and horizontal layout.
* Windows installer: Make the "add interpreter" shortcut run as administrator
  if needed.
* Add history-up and history-down accelerators suitable for the Mac.

What's new in DreamPie 1.1
--------------------------

DreamPie 1.1 was released on 2010/07/14, and adds a bunch of cool features:

* AutoParen will automatically type parentheses and possible quotes when you
  press the space key after a function or a method. For example,
  type "`open hello`" and you'll get "`open("hello")`", saving you a total of
  seven keystrokes! This lets you create "magic functions" that are very easy
  to use.

  (Did you know that you can automatically import your frequently used functions?
  Check the "execute code" box in the shell tab of the configuration window.)

* Enhanced function documentation will show you the complete docstring and
  source code of a function (if available), and can be scrolled easily.

* AutoComplete will now complete module names, module members, and function
  argument names.

And some additional features:

* A new "configure interpreter" command on the Windows installation lets you
  easily configure additional Python interpreters such as Jython and IronPython.
* The list of recent history files is shown.
* The behavior of the tab key when an AutoComplete list is shown is more consistent.
* Errors when starting the subprocess are now reported, instead of DreamPie just
  being stuck.
