# UPLB in Roblox

A Roblox remake of the University of the Philippines Los Baños (UPLB) campus.

## Project Structure
This project is structured using [Rojo](https://rojo.space/), allowing development to happen in an external code editor (like VS Code) while syncing to Roblox Studio.

* `src/Client/` - Code that runs on the player's device (UI, inputs, local effects). Syncs to `StarterPlayerScripts`.
* `src/Server/` - Code that runs on the Roblox server (data saving, economy, authority). Syncs to `ServerScriptService`.
* `src/Shared/` - Code shared between the client and server (constants, utility functions). Syncs to `ReplicatedStorage`.

## Getting Started
1. Install [Rojo](https://rojo.space/docs/v7/getting-started/installation/).
2. Run `rojo serve` in this directory to start the Rojo server.
3. Open a new place in Roblox Studio.
4. Install the Rojo plugin for Roblox Studio and connect to the server.
5. All code changes in your code editor will now instantly sync into Roblox Studio!
