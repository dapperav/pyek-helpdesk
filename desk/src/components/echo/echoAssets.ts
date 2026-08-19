// Echo Finley pose stickers (Mark's ChatGPT art, 2026-08-19). 200px
// transparent PNGs bundled as hashed vite assets — no /files dependency,
// so they work on the dev server and version with the app. The classic
// avatar keeps its jobs in emails and the ticket feed
// (/files/echo-finley.png).
import cheer from "@/assets/echo/echo-cheer.png";
import clock from "@/assets/echo/echo-clock.png";
import echoFloat from "@/assets/echo/echo-float.png";
import hello from "@/assets/echo/echo-hello.png";
import lost from "@/assets/echo/echo-lost.png";
import night from "@/assets/echo/echo-night.png";
import ok from "@/assets/echo/echo-ok.png";
import peek from "@/assets/echo/echo-peek.png";
import search from "@/assets/echo/echo-search.png";
import serious from "@/assets/echo/echo-serious.png";
import thumbs from "@/assets/echo/echo-thumbs.png";

export const ECHO_POSES = {
  cheer,
  clock,
  float: echoFloat,
  hello,
  lost,
  night,
  ok,
  peek,
  search,
  serious,
  thumbs,
} as const;

export type EchoPose = keyof typeof ECHO_POSES;
