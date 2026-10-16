-- yit listening tracker: runs inside the mpv daemon and appends one JSON line
-- per finished track to ~/.yit/plays.jsonl, so yit can learn what you like.
-- Captures queue auto-advance, skips (playlist-next) and stops, which the
-- short-lived yit CLI process can't see.
local utils = require "mp.utils"

local log_path = mp.get_opt("yit_tracker-log")
if not log_path or log_path == "" then return end

local cur = nil
local last_pos = nil

local function flush(reason)
    if not cur then return end
    local rec = {
        ts = os.time(),
        started = cur.started,
        url = cur.url,
        title = cur.title,
        duration = cur.duration,
        listened = math.floor(cur.listened + 0.5),
        reason = reason or "unknown",
    }
    cur = nil
    last_pos = nil
    local json = utils.format_json(rec)
    if not json then return end
    local f = io.open(log_path, "a")
    if f then
        f:write(json, "\n")
        f:close()
    end
end

mp.register_event("file-loaded", function()
    flush("replaced")  -- safety: previous entry never got an end-file
    cur = {
        url = mp.get_property("path") or "",
        title = mp.get_property("media-title") or "",
        duration = mp.get_property_number("duration", 0),
        listened = 0,
        started = os.time(),
    }
    last_pos = nil
end)

mp.observe_property("media-title", "string", function(_, v)
    if cur and v and v ~= "" then cur.title = v end
end)

mp.observe_property("duration", "number", function(_, v)
    if cur and v and v > 0 then cur.duration = v end
end)

-- Accumulate real listening time; ignore jumps (seeks) and paused time.
mp.observe_property("playback-time", "number", function(_, v)
    if not cur or not v then return end
    if last_pos then
        local d = v - last_pos
        if d > 0 and d < 5 then cur.listened = cur.listened + d end
    end
    last_pos = v
end)

mp.register_event("end-file", function(e)
    flush(e and e.reason or "unknown")
end)

mp.register_event("shutdown", function()
    flush("quit")
end)
