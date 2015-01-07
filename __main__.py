#!/usr/bin/python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

import os
import sys
import wstund

if __name__ == "__main__":
    # print("uid {0}".format(os.getuid()))
    if os.getuid() is not 0:
        os.execvp("sudo", ["sudo", "python2"] + sys.argv)
    wstund.main()
