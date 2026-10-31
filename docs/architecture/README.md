# Editing the architecture diagrams

| Diagram | Source | Image |
| --- | --- | --- |
| Architecture overview | `overview.svg` (hand-drawn SVG, edit the file directly) | `overview.svg` |
| Class diagram | `class.puml` | `class.svg` |
| Sequence: live detection | `seq-detection.puml` | `seq-detection.svg` |
| Sequence: mode switch | `seq-mode-switch.puml` | `seq-mode-switch.svg` |
| Sequence: back-fill | `seq-backfill.puml` | `seq-backfill.svg` |
| Use cases | `use-cases.puml` | `use-cases.svg` |

All PlantUML diagrams share the colours and fonts in `style.iuml`; the sequence diagrams also use `seq-style.iuml`. Colours mean the same in every diagram: blue = pipeline service, amber = Kafka/storage, green = carbon control and evaluation, purple = monitoring, grey = outside the cluster.

## Re-export after editing

The `.svg` files are snapshots, so export them again after changing a `.puml` file. Download the [PlantUML jar](https://plantuml.com/download) (needs Java) and run from this folder:

```powershell
java -jar C:\path\to\plantuml.jar -charset UTF-8 -tsvg class.puml use-cases.puml seq-*.puml
```

No Graphviz is needed: the class and use-case diagrams use PlantUML's built-in Smetana layout. In VS Code, the [PlantUML extension](https://github.com/qjebbs/vscode-plantuml) shows a live preview with `Alt+D`.

## Technical references

- [GEOFON SeedLink service](https://geofon.gfz.de/waveform/seedlink.php)
- [SeisBench waveform models](https://seisbench.readthedocs.io/en/latest/pages/documentation/models/waveform_models.html)
- [ObsPy STA/LTA trigger tutorial](https://docs.obspy.org/tutorial/code_snippets/trigger_tutorial.html)
- [EMSC](https://www.emsc-csem.org/)
- [Kafka documentation](https://kafka.apache.org/documentation/)
- [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Prometheus overview](https://prometheus.io/docs/introduction/overview/)
- [CodeCarbon methodology](https://docs.codecarbon.io/3.3/explanation/methodology/)
