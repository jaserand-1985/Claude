# Dead Tide

A 3D zombie lane shooter for Android phones. Your squad charges down a road through one of five maps: a highway bridge, a downtown street, a pine forest, a desert highway or the Dead Woods. Steer through number gates to grow your squad, shoot crates open for power-ups, mow down the hordes, and take down a giant boss at the end of every level.

## How to play

- **Steer:** drag left and right anywhere on the screen. On a computer, use A/D or the arrow keys.
- **Shoot:** automatic. Every soldier fires forward; your squad leader carries a minigun.
- **Gates:** each gate has two halves. Blue halves add or multiply soldiers (`+8`, `×2`); red halves remove or divide them (`−6`, `÷2`). You pass through whichever half you are lined up with. Shooting an add/subtract half raises its number, so a red gate can be turned blue.
- **Zombies:** every zombie that reaches your squad takes a soldier with it. Brutes (big and purple) take three. If your whole squad falls, the run is over.
- **Boss:** at the end of the bridge your squad stops and the boss walks in. Its stomps knock out soldiers, so kill it fast.
- **Armory:** coins from kills, survivors and bosses buy permanent upgrades between levels.

### Maps

| Map | Ground and scenery |
| --- | --- |
| Highway Bridge | Elevated highway over water, glass towers |
| Downtown | Paved sidewalks and curbs, brick buildings, streetlights, traffic lights, bollards, crosswalks, wrecked cars |
| Pine Forest | Dirt road, grass, pines and autumn trees, ferns, bushes, rocks |
| Desert Highway | Sand and dunes, sandstone rocks and mesas, guard rails, telephone poles with wires |
| Dead Woods | Dead and twisted trees, a roadside graveyard, iron fence, red dusk |

The **MAP** button in the Armory picks a map, or AUTO to change map every level.

### Weapons

| Weapon | Unlocks | How it fights |
| --- | --- | --- |
| Rifle | start | Fast, accurate tracers |
| Shotgun | level 2 | Five-pellet blasts, deadly up close |
| Rocket launcher | level 3 | Real rockets with smoke trails; the blast blows zombies apart |
| Flamethrower | level 4 | A long jet of fire that reaches about 12 m ahead, splashes burning fuel on the road and sets zombies burning until they char |

The **WEAPON** button in the Armory sets the starting weapon. Weapon crates on the road switch the whole squad's weapon for the rest of the level. The squad leader always carries the minigun.

### Power-up crates

Shoot a crate until its number reaches zero to open it.

| Crate | Effect |
| --- | --- |
| Rapid | Fire rate ×2.4 for 8 seconds |
| Spread | Every shot fires three bullets for 8 seconds |
| Shotgun / Rockets / Flamer | Switch the squad to that weapon |
| Shield | Zombies die on contact instead of taking soldiers, 7 seconds |
| Freeze | Zombies slow to a crawl for 6 seconds |
| Airstrike | A line of explosions sweeps the road ahead |
| + Men | Instant reinforcements |

### Armory upgrades

Firepower (+20% damage), Fire Rate (+10%), Recruits (+1 starting soldier), Scavenger (+25% coins).

## Install on Android

The GitHub Actions workflow in `.github/workflows/android.yml` builds an APK on every push.

1. On your phone, open this repository's **Releases** page and open the `Dead Tide (<branch>)` release.
2. Tap **DeadTide.apk** to download it, then open the downloaded file.
3. The first time, Android asks you to allow installing apps from your browser. Allow it, then tap **Install**.

The APK is a debug build. It installs fine by sideloading, but it is not signed for the Play Store.

## Project layout

- `www/index.html`: the whole game (WebGL with three.js r170). Serve the `www` folder over HTTP to play in a browser (`python3 -m http.server` inside `www`).
- `www/lib/`: three.js, bundled so the app works offline.
- `www/models/`: baked character data (soldier and zombie): geometry, colours, body-part groups and every animation frame stored as a half-float texture; `zombie-gibs.json` holds the body-part chunks.
- `tools/bake/`: the baking tool that turns the rigged `.glb` models into `www/models/` (also builds the rifle, minigun, shotgun, rocket launcher and flamethrower).
- `www/scenery/`: map scenery as small GLB files, made by `tools/scenery` from Quaternius's CC0 Downtown City MegaKit, Stylized Nature MegaKit and Street Pack (mirrored at github.com/tilakpatell/tilakverse-assets): hidden interiors removed, textures shrunk to 512 px, normal and roughness maps dropped.
- `www/fonts/`: bundled fonts so the app works offline.
- `android/`: the Capacitor Android project (portrait lock, full-screen, screen kept awake, app icon and splash).
- `capacitor.config.json`, `package.json`: Capacitor setup.

## Characters and animation

The soldiers and zombies are rigged, animated low-poly models by [Quaternius](https://quaternius.com) from the Ultimate Animated Character Pack, released under CC0 (public domain); see `www/models/QUATERNIUS-LICENSE.txt`.

To draw hundreds of animated characters on a phone, the game uses vertex animation textures: `tools/bake` plays each clip (Run_Carry, Walk_Carry, Punch, Death, Victory) and records every vertex position at 15 frames per second into a texture. The game then draws each crowd with a single instanced draw call, and the vertex shader reads and blends the two nearest frames. The bake also attaches the rifle and minigun, recolours a few materials and normalises size and facing.

Re-bake after changing models or clips:

```sh
python3 -m http.server 8766   # from the repository root
node tools/bake/run-bake.js   # writes www/models/*.bin and *.json
```

## Sound, effects and lighting

- **Sound:** every effect is a real recording (CC0): AK-47, SMG and PPSh-41 shots from The Free Firearm Sound Library, layered explosions, a missile launch, undead moans and groans, and a battlefield ambience loop. Credits per file are in `www/audio/CREDITS.md`. The Web Audio mixer adds a reverb tail, a compressor, stereo panning by position, distance muffling and voice limits.
- **Explosions:** billboard fire and smoke puffs drawn with a custom shader (cloud noise that erodes with age, fire that cools from white to orange to red, smoke lit from above), a dust ring, sparks, burning debris with smoke trails, scorch marks and a point-light flash that lights the road and characters.
- **Hits and gore:** zombies flinch and get knocked back when shot (the model's own hit-reaction animation). Kills can take the head or an arm off: the bake splits the zombie mesh into head, arms, legs and torso by bone, so the part disappears from the body (whose insides render red) and a real chunk of the model tumbles away, bounces and bleeds. Explosions blow walkers apart and throw brutes. Blood is glossy droplets that fall and stain the road, splatter decals with streaks, and pools that spread under the bodies.
- **Lighting:** image-based lighting from the sky, real-time shadows from every character, a rim light on characters, HDR bloom, MSAA and a colour grade with vignette.
- **Graphics setting:** HIGH or LOW in the menu and pause screen. On first play, the game drops to LOW automatically if HIGH runs below about 40 fps.

## Build the APK yourself

You need Node 22, JDK 21 and the Android SDK (platform 35).

```sh
npm install
npx cap sync android
cd android && ./gradlew assembleDebug
# APK: android/app/build/outputs/apk/debug/app-debug.apk
```
