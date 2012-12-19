# -*- coding: utf-8 -*-
# Copyright (c) 2011, Sebastian Wiesner <lunaryorn@gmail.com>
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
    synaptiks.kde.widgets.util
    ==========================

    Utility widgets.

    .. moduleauthor::  Sebastian Wiesner  <lunaryorn@gmail.com>
"""

from __future__ import (print_function, division, unicode_literals,
                        absolute_import)

from PyKDE4.kdecore import i18nc
from PyKDE4.kdeui import KComboBox


class MouseButtonComboBox(KComboBox):
    """
    A combox box, which provides a choice between different mouse buttons.
    """

    def __init__(self, parent=None):
        KComboBox.__init__(self, parent)
        self.addItems([
            i18nc('@item:inlistbox mouse button triggered by tapping',
                  'Disabled'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                  'Left mouse button'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                  'Middle mouse button'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Right mouse button'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Scroll up'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Scroll down'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Scroll left'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Scroll right'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Previous location'),
            i18nc('@item:inlistbox mouse button triggered by tapping',
                   'Next location')
            ])
