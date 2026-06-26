"""Main entry point for the Python scientific computing tool."""

import multiprocessing

from 前端.bootstrap import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
