{ pkgs }: {
  deps = [
    pkgs.python310Full
    pkgs.python310Packages.aiogram
    pkgs.python310Packages.aiohttp
    pkgs.python310Packages.requests
    pkgs.ffmpeg
  ];
}
