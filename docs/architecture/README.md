# Viewing and editing the architecture diagrams

The architecture overview is intentionally short; the three diagrams are expandable supporting material. Markdown has no fixed paper size, so printed pagination depends on the viewer.

- **View immediately:** open `ARCHITECTURE.md` with VS Code's **Markdown: Open Preview to the Side** command (`Ctrl+K V`), then expand a diagram. The embedded SVG files need no PlantUML extension. You can also open the SVGs directly in a browser.
- **Edit and preview PlantUML:** install the [PlantUML extension by jebbs](https://github.com/qjebbs/vscode-plantuml), open a `.puml` file, and press `Alt+D`. Its local renderer requires Java and may require Graphviz depending on the chosen layout engine. These component/use-case sources select PlantUML's bundled Smetana layout engine.
- **Why the original code blocks did not render:** `@startuml` is PlantUML source. A Markdown code fence displays text unless the preview has PlantUML rendering support. Valid source is not itself a rendered image.
- **Refresh the SVGs after edits:** use the extension's export command, or run the following from the repository root with a downloaded [PlantUML JAR](https://plantuml.com/download):

```powershell
java -jar C:\path\to\plantuml.jar -tsvg docs/architecture/*.puml
```

The SVGs are generated snapshots; editing a source does not automatically update its image unless you export it again. No application services or GitHub Actions workflows are implemented by this proposal.

## Technical references

- [GEOFON SeedLink service](https://geofon.gfz.de/waveform/seedlink.php): live waveform feeds, Mini-SEED records and station metadata.
- [SeisBench waveform models](https://seisbench.readthedocs.io/en/latest/pages/documentation/models/waveform_models.html): PhaseNet and EQTransformer interfaces and model-specific settings.
- [ObsPy STA/LTA trigger tutorial](https://docs.obspy.org/tutorial/code_snippets/trigger_tutorial.html): short/long window triggering.
- [EMSC](https://www.emsc-csem.org/): earthquake catalogue provider.
- [RabbitMQ introduction](https://www.rabbitmq.com/tutorials/tutorial-one-python): producers, queues, consumers and message delivery.
- [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/): rolling updates and rollback. QuakeShift's proposed controller must detect failed rollouts and explicitly request restoration; Kubernetes does not automatically roll back a stalled Deployment.
- [GitHub self-hosted runners](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners): running workflows on hardware with local-cluster access.
- [Prometheus overview](https://prometheus.io/docs/introduction/overview/): metric collection, time series and queries.
- [CodeCarbon methodology](https://docs.codecarbon.io/3.3/explanation/methodology/): CPU/GPU/RAM measurement or estimation and attribution limits. Estimates do not cover every source of system energy use.

All deployment profiles, controller behavior, metric exporters and CI/CD steps in this document are proposed implementation work.
