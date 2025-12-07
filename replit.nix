{ pkgs }: {
  deps = [
    pkgs.ffmpeg
    pkgs.nodejs-18_x
    pkgs.nodePackages.npm
  ];
}
