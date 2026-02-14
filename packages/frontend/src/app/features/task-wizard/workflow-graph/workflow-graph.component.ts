import { Component, computed, effect, input, output, signal } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { FormDefinition } from '../../../core/models/task.model';

interface GraphNode {
  form: FormDefinition;
  x: number;
  y: number;
}

interface GraphEdge {
  path: string;
}

interface GraphLayout {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
  viewBox: string;
}

@Component({
  selector: 'app-workflow-graph',
  standalone: true,
  imports: [TitleCasePipe, MatCardModule, MatFormFieldModule, MatSelectModule, MatIconModule],
  template: `
    <div class="workflow-grid">
      <div class="workflow-controls">
        @for (form of workflowForms(); track form.step_order) {
          <mat-card class="step-card">
            <div class="step-title-row">
              <div class="step-title">
                <span class="step-badge">Step {{ form.step_order }}</span>
                <strong>{{ form.form_type | titlecase }}</strong>
              </div>
              <span class="page-url" [title]="form.page_url">{{ form.page_url }}</span>
            </div>

            @if (editable()) {
              <mat-form-field appearance="outline" class="dependency-field">
                <mat-label>Depends On</mat-label>
                <mat-select
                  [value]="form.depends_on_step_order"
                  (selectionChange)="onDependencyChange(form.step_order, $event.value)">
                  <mat-option [value]="null">Root Node</mat-option>
                  @for (option of dependencyOptions(form.step_order); track option.step_order) {
                    <mat-option [value]="option.step_order">
                      Step {{ option.step_order }} · {{ option.form_type | titlecase }}
                    </mat-option>
                  }
                </mat-select>
              </mat-form-field>
            } @else {
              <div class="dependency-readonly">
                <mat-icon>link</mat-icon>
                @if (form.depends_on_step_order !== null) {
                  <span>Depends on step {{ form.depends_on_step_order }}</span>
                } @else {
                  <span>Root node</span>
                }
              </div>
            }
          </mat-card>
        }
      </div>

      <div class="workflow-canvas">
        <svg [attr.viewBox]="layout().viewBox" [attr.width]="layout().width" [attr.height]="layout().height">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L10,5 L0,10 z" fill="#2878b8"></path>
            </marker>
          </defs>

          @for (edge of layout().edges; track edge.path) {
            <path [attr.d]="edge.path" class="edge"></path>
          }

          @for (node of layout().nodes; track node.form.step_order) {
            <g [attr.transform]="'translate(' + node.x + ',' + node.y + ')'">
              <rect
                width="210"
                height="66"
                rx="14"
                class="node"
                [attr.data-type]="node.form.form_type"></rect>
              <text x="14" y="28" class="node-title">Step {{ node.form.step_order }} · {{ node.form.form_type | titlecase }}</text>
              <text x="14" y="48" class="node-subtitle" [attr.title]="node.form.page_url">{{ trimLabel(node.form.page_url) }}</text>
            </g>
          }
        </svg>
      </div>
    </div>
  `,
  styles: [`
    .workflow-grid {
      display: grid;
      grid-template-columns: minmax(300px, 36%) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .workflow-controls {
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-height: 520px;
      overflow: auto;
      padding-right: 4px;
    }
    .step-card {
      border: 1px solid #c9e0f2;
      box-shadow: none;
      border-radius: 12px;
      background: linear-gradient(180deg, #ffffff 0%, #f6fbff 100%);
      padding: 10px;
    }
    .step-title-row {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .step-title {
      display: flex;
      gap: 8px;
      align-items: center;
      color: #0f3354;
    }
    .step-badge {
      font-size: 11px;
      font-weight: 700;
      color: #1f6ea9;
      background: #dcefff;
      border: 1px solid #b7d6ef;
      border-radius: 999px;
      padding: 2px 8px;
      line-height: 1.4;
    }
    .page-url {
      font-size: 12px;
      color: #376285;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .dependency-field {
      width: 100%;
      margin-top: 8px;
    }
    .dependency-readonly {
      margin-top: 8px;
      font-size: 13px;
      color: #1f5178;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .workflow-canvas {
      border: 1px solid #c9dcec;
      border-radius: 14px;
      background: radial-gradient(circle at 20% 10%, #f6fcff 0%, #edf7ff 42%, #f8fcff 100%);
      overflow: auto;
      min-height: 320px;
      padding: 8px;
    }
    svg {
      display: block;
      min-width: 700px;
    }
    .edge {
      fill: none;
      stroke: #2878b8;
      stroke-width: 2.5;
      marker-end: url(#arrow);
      opacity: 0.92;
    }
    .node {
      stroke: #1f6ea9;
      stroke-width: 1.4;
      fill: #ffffff;
      filter: drop-shadow(0 3px 6px rgba(19, 81, 126, 0.12));
    }
    .node[data-type='login'] {
      fill: #e8f4ff;
      stroke: #2d84c4;
    }
    .node[data-type='intermediate'] {
      fill: #edf9f2;
      stroke: #3b9a67;
    }
    .node[data-type='target'] {
      fill: #fff8ea;
      stroke: #d49330;
    }
    .node-title {
      font-size: 13px;
      font-weight: 700;
      fill: #0f3557;
    }
    .node-subtitle {
      font-size: 11px;
      fill: #3a5f7f;
    }
    @media (max-width: 1023px) {
      .workflow-grid {
        grid-template-columns: 1fr;
      }
      .workflow-controls {
        max-height: 360px;
      }
      svg {
        min-width: 620px;
      }
    }
  `],
})
export class WorkflowGraphComponent {
  forms = input<FormDefinition[]>([]);
  editable = input<boolean>(true);
  formsChange = output<FormDefinition[]>();

  workflowForms = signal<FormDefinition[]>([]);

  constructor() {
    effect(() => {
      this.workflowForms.set(this.normalizeForms(this.forms()));
    });
  }

  layout = computed<GraphLayout>(() => this.buildLayout(this.workflowForms()));

  dependencyOptions(stepOrder: number): FormDefinition[] {
    return this.workflowForms()
      .filter((form) => form.step_order !== stepOrder)
      .sort((a, b) => a.step_order - b.step_order);
  }

  onDependencyChange(stepOrder: number, dependency: number | null): void {
    const next = this.workflowForms().map((form) => {
      if (form.step_order !== stepOrder) {
        return form;
      }
      return {
        ...form,
        depends_on_step_order: dependency,
      };
    });

    this.workflowForms.set(this.normalizeForms(next));
    this.formsChange.emit(this.workflowForms());
  }

  trimLabel(url: string): string {
    return url.length > 34 ? `${url.slice(0, 31)}...` : url;
  }

  private normalizeForms(forms: FormDefinition[]): FormDefinition[] {
    const sorted = [...forms]
      .map((form) => ({
        ...form,
        depends_on_step_order: form.depends_on_step_order ?? null,
      }))
      .sort((a, b) => a.step_order - b.step_order);

    const stepSet = new Set(sorted.map((form) => form.step_order));

    return sorted.map((form) => {
      if (form.depends_on_step_order === form.step_order) {
        return { ...form, depends_on_step_order: null };
      }
      if (form.depends_on_step_order !== null && !stepSet.has(form.depends_on_step_order)) {
        return { ...form, depends_on_step_order: null };
      }
      return form;
    });
  }

  private buildLayout(forms: FormDefinition[]): GraphLayout {
    if (!forms.length) {
      return {
        nodes: [],
        edges: [],
        width: 760,
        height: 280,
        viewBox: '0 0 760 280',
      };
    }

    const byStep = new Map(forms.map((form) => [form.step_order, form]));
    const depthCache = new Map<number, number>();

    const depthFor = (stepOrder: number, stack = new Set<number>()): number => {
      if (depthCache.has(stepOrder)) {
        return depthCache.get(stepOrder)!;
      }
      if (stack.has(stepOrder)) {
        return 0;
      }

      const node = byStep.get(stepOrder);
      if (!node || node.depends_on_step_order === null || !byStep.has(node.depends_on_step_order)) {
        depthCache.set(stepOrder, 0);
        return 0;
      }

      stack.add(stepOrder);
      const depth = depthFor(node.depends_on_step_order, stack) + 1;
      stack.delete(stepOrder);
      depthCache.set(stepOrder, depth);
      return depth;
    };

    const grouped = new Map<number, FormDefinition[]>();
    let maxDepth = 0;

    for (const form of forms) {
      const depth = depthFor(form.step_order);
      maxDepth = Math.max(maxDepth, depth);
      if (!grouped.has(depth)) {
        grouped.set(depth, []);
      }
      grouped.get(depth)!.push(form);
    }

    const levelSpacing = 280;
    const rowSpacing = 128;
    const originX = 40;
    const originY = 28;

    const nodes: GraphNode[] = [];
    const positionByStep = new Map<number, { x: number; y: number }>();
    let maxRows = 0;

    for (let depth = 0; depth <= maxDepth; depth++) {
      const level = [...(grouped.get(depth) ?? [])].sort((a, b) => a.step_order - b.step_order);
      maxRows = Math.max(maxRows, level.length);

      level.forEach((form, row) => {
        const x = originX + depth * levelSpacing;
        const y = originY + row * rowSpacing;
        nodes.push({ form, x, y });
        positionByStep.set(form.step_order, { x, y });
      });
    }

    const edges: GraphEdge[] = [];
    for (const form of forms) {
      if (form.depends_on_step_order === null) {
        continue;
      }
      const parent = positionByStep.get(form.depends_on_step_order);
      const child = positionByStep.get(form.step_order);
      if (!parent || !child) {
        continue;
      }

      const startX = parent.x + 210;
      const startY = parent.y + 33;
      const endX = child.x;
      const endY = child.y + 33;
      const controlX = (startX + endX) / 2;

      edges.push({
        path: `M ${startX} ${startY} C ${controlX} ${startY} ${controlX} ${endY} ${endX} ${endY}`,
      });
    }

    const width = Math.max(760, originX + (maxDepth + 1) * levelSpacing + 60);
    const height = Math.max(280, originY + Math.max(maxRows, 1) * rowSpacing + 40);

    return {
      nodes,
      edges,
      width,
      height,
      viewBox: `0 0 ${width} ${height}`,
    };
  }
}
