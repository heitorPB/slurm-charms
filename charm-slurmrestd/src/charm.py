#!/usr/bin/python3
"""SlurmrestdCharm."""
import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmOpsManager
from slurmrestd_requires import SlurmrestdRequires


logger = logging.getLogger()


class SlurmrestdCharm(CharmBase):
    """Operator charm responsible for lifecycle operations for slurmctld."""

    _stored = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)
        self._stored.set_default(
            slurm_config=dict(),
            slurm_installed=False,
            slurmctld_available=False,
            munge_key=str(),
        )
        self.slurm_ops_manager = SlurmOpsManager(self, "slurmrestd")
        self._slurmrestd = SlurmrestdRequires(self, 'slurmrestd')

        event_handler_bindings = {
            self.on.install:
            self._on_install,

            self.on.start:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.slurmctld_available:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.slurmctld_unavailable:
            self._on_check_status_and_write_config,

            self._slurmrestd.on.munge_key_available:
            self._on_render_munge_key,

        }
        for event, handler in event_handler_bindings.items():
            self.framework.observe(event, handler)

    def _on_install(self, event):
        self.slurm_ops_manager.install()
        self.slurm_ops_manager.open_port()
        self.unit.status = ActiveStatus("slurm installed")
        self._stored.slurm_installed = True

    def _on_render_munge_key(self, event):
        if not self._check_status():
            event.defer()
            return

        self.slurm_ops_manager.write_munge_key_and_restart(
            self._stored.munge_key
        )
        self._on_check_status_and_write_config(event)

    def _on_check_status_and_write_config(self, event):
        if not self._check_status():
            event.defer()
            return
        config = dict(self._stored.slurm_config)
        self.slurm_ops_manager.render_config_and_restart(config)
        self.unit.status = ActiveStatus("Slurmrestd Available")

    def _check_status(self):
        slurm_installed = self._stored.slurm_installed
        slurmctld_acquired = self._stored.slurmctld_available
        slurm_config = self._stored.slurm_config
        munge_key = self._stored.munge_key

        if not (slurm_installed and slurmctld_acquired and
                slurm_config and munge_key):
            if not slurmctld_acquired:
                self.unit.status = BlockedStatus("NEED RELATION TO SLURMCTLD")
            elif not slurm_config:
                self.unit.status = BlockedStatus("NEED SLURM CONFIG")
            elif not munge_key:
                self.unit.status = BlockedStatus("NEED MUNGE KEY")
            else:
                self.unit.status = BlockedStatus("SLURM NOT INSTALLED")
            return False
        return True

    def is_slurmctld_available(self):
        """Return self._stored.slurmctld_available."""
        return self._stored.slurmctld_available

    def set_slurm_config(self, slurm_config):
        """Set self._stored.slurm_config."""
        self._stored.slurm_config = slurm_config

    def set_slurmctld_available(self, slurmctld_available):
        """Set self._stored.slurmctld_available."""
        self._stored.slurmctld_available = slurmctld_available

    def set_munge_key(self, munge_key):
        """Set self._stored.munge_key."""
        self._stored.munge_key = munge_key


if __name__ == "__main__":
    main(SlurmrestdCharm)
