# Anime4u-Live-Bot

---

## Auto HLS Remux + Supabase (new)

When `AUTO_HLS=true`, every video file you send
(`.mkv`, `.mp4`, `.avi`, `.webm`, `.mov`, `.m4v`)
is automatically:

1. Downloaded from Telegram
2. Remuxed to HLS with FFmpeg (`-c:v copy`, audio -> AAC)
3. Uploaded to B2 under `<selected-folder>/<video-name>/`
4. Inserted as a row in your Supabase `streams` table,
   so it appears on your streaming site immediately

Non-video documents upload unchanged, as before.

### Server requirements

- `ffmpeg` must be installed (`apt install ffmpeg`)
- Supabase table:

```sql
create table streams (
  id uuid default gen_random_uuid() primary key,
  title text not null,
  video_url text not null,
  is_live boolean default true,
  created_at timestamptz default now()
);
```

### B2 CORS

Make sure your bucket CORS allows your website origin
so the browser can fetch `.m3u8` / `.ts` files.
