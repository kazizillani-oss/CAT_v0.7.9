"""
calc_terminal.ui — the single owner of every interactive interface.

Contains only rendering + event dispatch: no chemistry logic, no AI
logic, no calculation logic. Business logic stays in the modules one
level up (aicore.py, permissions.py, session.py, engine.py, ...); this
package renders their state and turns user interaction into events.
"""
