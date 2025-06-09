# -*- coding: utf-8 -*-
"""
Exceptions personnalisées pour l'application Olex2RTZ.
"""

class Olex2RtzError(Exception):
    """Classe de base pour les exceptions de l'application."""
    pass

class InvalidFileError(Olex2RtzError):
    """Levée lorsqu'un fichier est invalide (décompression, format, etc.)."""
    pass

class NoRoutesFoundError(Olex2RtzError):
    """Levée si aucune route valide n'est trouvée dans le fichier."""
    pass