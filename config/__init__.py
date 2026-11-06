"""
Inicialización del proyecto Django con soporte para MySQL / MariaDB mediante PyMySQL.
Permite utilizar el motor 'django.db.backends.mysql' de forma nativa en Python 3.
"""

import pymysql

pymysql.install_as_MySQLdb()

