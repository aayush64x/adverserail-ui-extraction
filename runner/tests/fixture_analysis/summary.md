# Results summary

> **WARNING: contains FAKE mock-model rows (marked FAKE). They exist only to test the pipeline and must never be reported as results.**

- Scored outputs: 36; API errors excluded: 0; unparseable outputs (scored as empty): 0
- Pages: 2; perturbations: P0, P2, P8
- `field_acc` = mean over 7 fields (handle exact, text similarity, link exact, image_text similarity, 3 counts exact); missing post = 0 on all fields. `post_f1` = post-level F1 after Hungarian alignment. `drop` = score(Pk) - score(P0), paired by page. Brackets = bootstrap 95% CI over pages (1000 resamples).

## Field accuracy by perturbation

| model / condition | P0 | P2 | P8 |
|---|---|---|---|
| mock-oracle-text / text_html (FAKE) | 0.957 | 0.982 | 0.958 |
| mock-oracle-text / text_inner (FAKE) | 0.957 | 0.554 | 0.955 |
| mock-oracle-vision / text_html (FAKE) | 1.000 | 0.976 | 0.976 |
| mock-oracle-vision / text_inner (FAKE) | 0.958 | 0.548 | 0.981 |
| mock-oracle-vision / vision (FAKE) | 0.982 | 1.000 | 0.924 |
| selector-scraper / dom_selectors | 0.958 | 0.958 | 0.958 |

## Robustness drop vs P0 (field_acc, 95% CI)

| model / condition | P2 | P8 | DOM_ATTACKS | VISUAL_ATTACKS | ALL_ATTACKS |
|---|---|---|---|---|---|
| mock-oracle-text / text_html (FAKE) | 0.025 [0.000, 0.049] | 0.002 [0.000, 0.003] | 0.025 [0.000, 0.049] | 0.002 [0.000, 0.003] | 0.013 [0.000, 0.026] |
| mock-oracle-text / text_inner (FAKE) | -0.403 [-0.428, -0.378] | -0.001 [-0.006, 0.003] | -0.403 [-0.428, -0.378] | -0.001 [-0.006, 0.003] | -0.202 [-0.217, -0.187] |
| mock-oracle-vision / text_html (FAKE) | -0.024 [-0.048, 0.000] | -0.024 [-0.048, 0.000] | -0.024 [-0.048, 0.000] | -0.024 [-0.048, 0.000] | -0.024 [-0.048, 0.000] |
| mock-oracle-vision / text_inner (FAKE) | -0.411 [-0.429, -0.393] | 0.023 [0.000, 0.045] | -0.411 [-0.429, -0.393] | 0.023 [0.000, 0.045] | -0.194 [-0.196, -0.192] |
| mock-oracle-vision / vision (FAKE) | 0.018 [0.000, 0.036] | -0.058 [-0.105, -0.011] | 0.018 [0.000, 0.036] | -0.058 [-0.105, -0.011] | -0.020 [-0.052, 0.013] |
| selector-scraper / dom_selectors | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |

## Post-level F1 and per-field accuracy (mean over all perturbations)

| model / condition | post_f1 | precision | recall | author_handle | text | link_url | image_text | replies | boosts | favourites | text_exact | order_tau |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mock-oracle-text / text_html (FAKE) | 1.000 | 1.000 | 1.000 | 1.000 | 0.995 | 1.000 | 0.764 | 1.000 | 1.000 | 1.000 | 0.889 | 0.833 |
| mock-oracle-text / text_inner (FAKE) | 1.000 | 1.000 | 1.000 | 1.000 | 0.989 | 1.000 | 0.764 | 0.667 | 0.667 | 0.667 | 0.819 | 0.667 |
| mock-oracle-vision / text_html (FAKE) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.889 | 1.000 | 1.000 | 1.000 | 1.000 | 0.889 |
| mock-oracle-vision / text_inner (FAKE) | 1.000 | 1.000 | 1.000 | 1.000 | 0.997 | 1.000 | 0.806 | 0.667 | 0.667 | 0.667 | 0.944 | 0.556 |
| mock-oracle-vision / vision (FAKE) | 1.000 | 1.000 | 1.000 | 1.000 | 0.976 | 0.944 | 0.944 | 1.000 | 1.000 | 0.917 | 0.667 | 1.000 |
| selector-scraper / dom_selectors | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.708 | 1.000 | 1.000 | 1.000 | 1.000 | 0.333 |

`order_tau` (diagnostic, not in field_acc): Kendall tau between output order and visual order of matched posts (1 = perfect top-to-bottom order).

Charts: `accuracy_by_perturbation.png`, `drop_heatmap.png`, `per_field.png`.
