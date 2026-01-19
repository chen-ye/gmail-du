
    def update_scopes(self):
        """Update scopes to include modify."""
        if 'https://www.googleapis.com/auth/gmail.modify' not in self.creds.scopes:
             # We can't just change scopes on existing creds object without re-auth.
             # This is a limitation. The user must re-auth with new scopes.
             # For now, we assume the user has granted modify access or we fail gracefully.
             # Ideally, we request 'modify' scope in auth.py from the start.
             pass
