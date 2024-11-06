# Start FPGA's Mic Server on Boot

# command to run on boot
# sudo wavdump -r -g 1

{ config, lib, pkgs, ... }:
{

    systemd.services.start-mic-recorder = {
      description = "Start Mic Recorder";

      wantedBy = [ "multi-user.target" ];
      after = [ "bitstream.service" ];

      serviceConfig = {
          Environment = "PYTHONUNBUFFERED=1";
          ExecStart = "${pkgs.design.application}/bin/recorder";
          User = "root";
          Group = "root";
      };
    };
}