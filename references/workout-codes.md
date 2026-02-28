# Workout Code Syntax / 课表代码格式

Reference for the `name` field when pushing plans via `push --name`.

## Format

Tasks are separated by `;`:

```
task1;task2;task3
```

### Single task

```
duration@(intensity_type+range)
```

Example: `30min@(HRR+1.0~2.0)`

### Intervals

```
{task1;task2}xN
```

Example: `{5min@(HRR+3.0~4.0);1min@(rest)}x3`

### Rest

```
duration@(rest)
```

Parentheses are required. Example: `2min@(rest)`

## Duration Units

| Unit | Meaning |
|------|---------|
| `min` | Minutes |
| `s` | Seconds |
| `m` | Meters |
| `km` | Kilometers |
| `c` | Reps (次) |

## Intensity Types

| Type | Description | Example |
|------|-------------|---------|
| `HRR` | Heart rate reserve zones (1.0–5.0) | `HRR+1.0~2.0` |
| `VDOT` | VDOT pace zones | `VDOT+4.0~5.0` |
| `PACE` | Absolute pace (min'sec, slow→fast) | `PACE+5'30~4'50` |
| `t/` | Threshold pace percentage | `t/0.88~0.99` |
| `MHR` | Max heart rate percentage | `MHR+0.85~0.95` |
| `LTHR` | Lactate threshold HR percentage | `LTHR+1.0~1.05` |
| `FTP` | Functional threshold power % (cycling) | `FTP+0.75~0.85` |
| `CP` | Absolute power in watts (cycling) | `CP+200~240` |
| `CSS` | Critical swim speed percentage | `CSS+0.95~1.05` |
| `TSP` | Threshold swim pace percentage | `TSP+0.95~1.05` |
| `EFFORT` | Effort level (0.0–1.0) | `EFFORT+0.8~1.0` |
| `OPEN` | Open/unstructured | `OPEN+1` |

## Weight (Intensity Label)

| Value | Label | Color |
|-------|-------|-------|
| `q1` | 高强度 (High) | 🔴 Red |
| `q2` | 中强度 (Medium) | 🟠 Orange |
| `q3` | 低强度 (Low) | 🟢 Green |
| `xuanxiu` | 选修/恢复 (Recovery) | 🔵 Blue |

## Type (Workout Category)

| Value | Label |
|-------|-------|
| `qingsong` | 轻松跑 Easy run |
| `xiuxi` | 休息日 Rest day |
| `e` | 有氧 Aerobic |
| `lsd` | 长距离 Long run |
| `m` | 马拉松配速 Marathon pace |
| `t` | 乳酸阈 Threshold |
| `i` | 间歇 Intervals |
| `r` | 速度 Speed |
| `ft` | 法特莱克 Fartlek |
| `com` | 组合 Combined |
| `ch` | 变速 Variable pace |
| `jili` | 肌力 Strength |
| `max` | 最大心率测试 Max HR test |
| `drift` | 有氧稳定测试 Aerobic drift test |
| `other` | 其他 Other |
| `1` | 1.6km test |
| `7` | 2km test |
| `2` | 3km test |
| `3` | 5km test |
| `4` | 10km test |
| `5` | Half marathon test |
| `6` | Full marathon test |

## Sports

| Value | Type |
|-------|------|
| `1` | 跑步 Running (default) |
| `2` | 骑行 Cycling |
| `3` | 肌力 Strength |
| `5` | 游泳 Swimming |
| `254` | 其他 Other |

## Examples

### Running (sports: 1)

Segmented (HRR zones):
```
10min@(HRR+1.0~2.0);40min@(HRR+2.0~3.0);10min@(HRR+1.0~2.0)
```

Intervals (VDOT pace):
```
10min@(HRR+1.0~2.0);{1000m@(VDOT+4.0~5.0);2min@(rest)}x5;10min@(HRR+1.0~2.0)
```

Absolute pace:
```
10min@(HRR+1.0~2.0);30min@(PACE+5'30~4'50);10min@(HRR+1.0~2.0)
```

MHR intervals:
```
10min@(HRR+1.0~2.0);{400m@(MHR+0.85~0.95);90s@(rest)}x8;10min@(HRR+1.0~2.0)
```

### Cycling (sports: 2)

FTP zones:
```
10min@(FTP+0.55~0.65);40min@(FTP+0.75~0.85);10min@(FTP+0.55~0.65)
```

FTP intervals:
```
10min@(FTP+0.55~0.65);{5min@(FTP+0.95~1.05);3min@(FTP+0.55~0.65)}x4;10min@(FTP+0.55~0.65)
```

### Swimming (sports: 5)

CSS zones:
```
200m@(CSS+0.80~0.90);1000m@(CSS+0.95~1.05);200m@(CSS+0.80~0.90)
```

CSS intervals:
```
200m@(CSS+0.80~0.90);{100m@(CSS+1.05~1.10);30s@(rest)}x8;200m@(CSS+0.80~0.90)
```

### Strength (sports: 3)

```
rest!10*3;kick!15*3;walk!20*3
```
