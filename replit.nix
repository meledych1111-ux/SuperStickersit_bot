{ pkgs }: {
  deps = [
    pkgs.nodejs_20
    pkgs.ffmpeg_6
    pkgs.ffmpeg
    pkgs.libwebp
    pkgs.libvpx
  ];
  
  env = {
    LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.ffmpeg
      pkgs.libwebp
      pkgs.libvpx
      pkgs.stdenv.cc.cc.lib
    ];
  };
}
