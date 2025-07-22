# Cecilia Homepage Widget

This directory contains the Homepage widget for Cecilia Discord Bot.

## Files

- `widget.js` - Widget definition and API endpoint mappings
- `component.jsx` - React component for rendering the widget
- `translations-en.json` - English translations for the widget

## Installation

To install this widget in your Homepage dashboard:

1. Copy the `widget.js` and `component.jsx` files to your Homepage `src/widgets/cecilia/` directory
2. Add the translations from `translations-en.json` to your Homepage common translations file
3. Register the widget in `src/widgets/widgets.js`:
   ```javascript
   import cecilia from "./cecilia/widget";
   
   const widgets = {
     // ...other widgets...
     cecilia: cecilia,
   };
   ```
4. Add the component to `src/widgets/components.js`:
   ```javascript
   const components = {
     // ...other components...
     cecilia: dynamic(() => import("./cecilia/component")),
   };
   ```

## Configuration

Add to your `services.yaml`:

```yaml
- Cecilia Bot:
    icon: cecilia.svg
    href: http://your-cecilia-server.com:8010
    description: Discord research assistant bot
    widget:
      type: cecilia
      url: http://your-cecilia-server.com:8010
```

## API Endpoints

The widget uses these endpoints from Cecilia:

- `/status` - Returns status of all Cecilia services (including Ollama)
- `/stats` - Returns bot statistics (uptime, commands processed, etc.)
- `/ollama` - Returns Ollama system resources (CPU/GPU usage, memory, processes)

## Displayed Information

The widget shows:
- **Active Services** - Number of online services (Discord bot, essay summarizer, message pusher, Ollama)
- **CPU Usage** - Current system CPU utilization percentage
- **GPU Usage** - Current GPU utilization (if GPU available, shows "No GPU" otherwise)
- **Ollama Status** - Status of Ollama service (Online/Offline/Error/Timeout)

## Requirements

- Cecilia must be running with the web server on port 8010 for the widget to function properly
- Ollama should be running on default port 11434 for monitoring
- Additional Python packages: `psutil>=5.9.0`, `GPUtil>=1.4.0` (for system monitoring)
