<?php

namespace Tests\Feature;

use App\Events\TaskStatusChanged;
use App\Jobs\ExecuteTaskJob;
use App\Models\FormDefinition;
use App\Models\FormField;
use App\Models\Task;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Queue;
use Laravel\Passport\Passport;
use Tests\TestCase;

class TaskTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::create([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => bcrypt('password123'),
        ]);

        Passport::actingAs($this->user);
    }

    // -----------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------

    private function createTask(array $overrides = []): Task
    {
        return Task::create(array_merge([
            'user_id' => $this->user->id,
            'name' => 'Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'draft',
        ], $overrides));
    }

    private function createTaskWithFormDefinitions(): Task
    {
        $task = $this->createTask();

        $fd = FormDefinition::create([
            'task_id' => $task->id,
            'step_order' => 1,
            'page_url' => 'https://example.com/login',
            'form_type' => 'login',
            'form_selector' => '#login-form',
            'submit_selector' => '#submit-btn',
        ]);

        FormField::create([
            'form_definition_id' => $fd->id,
            'field_name' => 'username',
            'field_type' => 'text',
            'field_selector' => '#username',
            'field_purpose' => 'username',
            'preset_value' => 'testuser',
            'is_sensitive' => false,
            'is_required' => true,
            'sort_order' => 0,
        ]);

        FormField::create([
            'form_definition_id' => $fd->id,
            'field_name' => 'password',
            'field_type' => 'password',
            'field_selector' => '#password',
            'field_purpose' => 'password',
            'preset_value' => 'encrypted-secret',
            'is_sensitive' => true,
            'is_required' => true,
            'sort_order' => 1,
        ]);

        return $task;
    }

    // -----------------------------------------------------------------
    // List tasks
    // -----------------------------------------------------------------

    public function test_list_tasks_returns_only_current_users_tasks(): void
    {
        $this->createTask(['name' => 'My Task 1']);
        // Small sleep to ensure different updated_at in SQLite
        usleep(10000);
        $this->createTask(['name' => 'My Task 2']);

        // Create another user's task
        $otherUser = User::create([
            'name' => 'Other User',
            'email' => 'other@example.com',
            'password' => bcrypt('password123'),
        ]);
        Task::create([
            'user_id' => $otherUser->id,
            'name' => 'Other Task',
            'target_url' => 'https://other.com',
            'status' => 'draft',
        ]);

        $response = $this->getJson('/api/tasks');

        $response->assertStatus(200)
            ->assertJsonCount(2, 'data');

        // Verify other user's task is not in the response
        $names = collect($response->json('data'))->pluck('name')->all();
        $this->assertNotContains('Other Task', $names);
        $this->assertContains('My Task 1', $names);
        $this->assertContains('My Task 2', $names);
    }

    public function test_list_tasks_can_filter_by_status(): void
    {
        $this->createTask(['name' => 'Active Task', 'status' => 'active']);
        $this->createTask(['name' => 'Draft Task', 'status' => 'draft']);

        $response = $this->getJson('/api/tasks?status=active');

        $response->assertStatus(200)
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Active Task');
    }

    /**
     * Note: The search feature uses PostgreSQL's `ilike` operator which is not
     * supported by SQLite. This test is marked to run only when a PostgreSQL
     * connection is configured. In SQLite-based test runs this test is skipped.
     */
    public function test_list_tasks_can_search_by_name(): void
    {
        if (config('database.default') === 'sqlite') {
            $this->markTestSkipped('Search uses PostgreSQL ilike operator which is not supported by SQLite.');
        }

        $this->createTask(['name' => 'Login Automation']);
        $this->createTask(['name' => 'Invoice Download']);

        $response = $this->getJson('/api/tasks?search=Login');

        $response->assertStatus(200)
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Login Automation');
    }

    public function test_list_tasks_is_paginated(): void
    {
        for ($i = 0; $i < 20; $i++) {
            $this->createTask(['name' => "Task {$i}"]);
        }

        $response = $this->getJson('/api/tasks?per_page=5');

        $response->assertStatus(200)
            ->assertJsonCount(5, 'data')
            ->assertJsonStructure([
                'data',
                'links',
                'meta' => ['current_page', 'last_page', 'per_page', 'total'],
            ])
            ->assertJsonPath('meta.total', 20)
            ->assertJsonPath('meta.per_page', 5);
    }

    // -----------------------------------------------------------------
    // Create task
    // -----------------------------------------------------------------

    public function test_create_task_with_valid_data(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'New Task',
            'target_url' => 'https://example.com/form',
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.name', 'New Task')
            ->assertJsonPath('data.target_url', 'https://example.com/form')
            ->assertJsonPath('data.user_id', $this->user->id)
            ->assertJsonPath('data.status', 'draft');

        $this->assertDatabaseHas('tasks', [
            'name' => 'New Task',
            'target_url' => 'https://example.com/form',
            'user_id' => $this->user->id,
        ]);
    }

    public function test_create_task_with_all_optional_fields(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Full Task',
            'target_url' => 'https://example.com/form',
            'schedule_type' => 'cron',
            'schedule_cron' => '0 */6 * * *',
            'status' => 'draft',
            'is_dry_run' => true,
            'max_retries' => 5,
            'max_parallel' => 3,
            'stealth_enabled' => false,
            'custom_user_agent' => 'FormBot/1.0',
            'action_delay_ms' => 1000,
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.schedule_type', 'cron')
            ->assertJsonPath('data.schedule_cron', '0 */6 * * *')
            ->assertJsonPath('data.is_dry_run', true)
            ->assertJsonPath('data.max_retries', 5)
            ->assertJsonPath('data.max_parallel', 3)
            ->assertJsonPath('data.stealth_enabled', false)
            ->assertJsonPath('data.custom_user_agent', 'FormBot/1.0')
            ->assertJsonPath('data.action_delay_ms', 1000);
    }

    public function test_create_task_with_form_definitions_and_fields(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Task With Forms',
            'target_url' => 'https://example.com/form',
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'page_url' => 'https://example.com/login',
                    'form_type' => 'login',
                    'form_selector' => '#login-form',
                    'submit_selector' => '#submit',
                    'form_fields' => [
                        [
                            'field_name' => 'email',
                            'field_type' => 'email',
                            'field_selector' => '#email',
                            'field_purpose' => 'email',
                            'preset_value' => 'user@test.com',
                            'is_sensitive' => false,
                            'is_required' => true,
                            'sort_order' => 0,
                        ],
                        [
                            'field_name' => 'password',
                            'field_type' => 'password',
                            'field_selector' => '#password',
                            'field_purpose' => 'password',
                            'preset_value' => 'secret123',
                            'is_sensitive' => true,
                            'is_required' => true,
                            'sort_order' => 1,
                        ],
                    ],
                ],
            ],
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.name', 'Task With Forms')
            ->assertJsonCount(1, 'data.form_definitions')
            ->assertJsonPath('data.form_definitions.0.form_type', 'login')
            ->assertJsonPath('data.form_definitions.0.form_selector', '#login-form')
            ->assertJsonCount(2, 'data.form_definitions.0.form_fields')
            ->assertJsonPath('data.form_definitions.0.form_fields.0.field_name', 'email')
            ->assertJsonPath('data.form_definitions.0.form_fields.1.field_name', 'password');

        // Verify data was persisted in the database
        $this->assertDatabaseHas('form_definitions', [
            'form_type' => 'login',
            'form_selector' => '#login-form',
        ]);
        $this->assertDatabaseHas('form_fields', [
            'field_name' => 'email',
        ]);
        $this->assertDatabaseHas('form_fields', [
            'field_name' => 'password',
        ]);

        // Verify the is_sensitive flag was stored correctly
        $emailField = FormField::where('field_name', 'email')->first();
        $this->assertFalse($emailField->is_sensitive);
        $sensitiveField = FormField::where('field_name', 'password')->first();
        $this->assertTrue($sensitiveField->is_sensitive);

        // Verify the sensitive field value was encrypted (not stored in plaintext)
        $passwordField = FormField::where('field_name', 'password')->first();
        $this->assertNotEquals('secret123', $passwordField->preset_value);
        $this->assertNotNull($passwordField->preset_value);
    }

    public function test_create_task_with_graph_dependencies(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Graph Task',
            'target_url' => 'https://example.com/root',
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'depends_on_step_order' => null,
                    'page_url' => 'https://example.com/root',
                    'form_type' => 'login',
                    'form_selector' => '#login-form',
                    'submit_selector' => '#login-submit',
                    'form_fields' => [],
                ],
                [
                    'step_order' => 2,
                    'depends_on_step_order' => 1,
                    'page_url' => 'https://example.com/branch-a',
                    'form_type' => 'target',
                    'form_selector' => '#branch-a-form',
                    'submit_selector' => '#branch-a-submit',
                    'form_fields' => [],
                ],
                [
                    'step_order' => 3,
                    'depends_on_step_order' => 1,
                    'page_url' => 'https://example.com/branch-b',
                    'form_type' => 'target',
                    'form_selector' => '#branch-b-form',
                    'submit_selector' => '#branch-b-submit',
                    'form_fields' => [],
                ],
            ],
        ]);

        $response->assertStatus(201);

        $formsByStep = collect($response->json('data.form_definitions'))->keyBy('step_order');
        $this->assertNull($formsByStep->get(1)['depends_on_step_order']);
        $this->assertEquals(1, $formsByStep->get(2)['depends_on_step_order']);
        $this->assertEquals(1, $formsByStep->get(3)['depends_on_step_order']);

        $taskId = $response->json('data.id');
        $this->assertDatabaseHas('form_definitions', [
            'task_id' => $taskId,
            'step_order' => 2,
            'depends_on_step_order' => 1,
        ]);
        $this->assertDatabaseHas('form_definitions', [
            'task_id' => $taskId,
            'step_order' => 3,
            'depends_on_step_order' => 1,
        ]);
    }

    public function test_create_task_rejects_form_definition_cycles(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Cyclic Task',
            'target_url' => 'https://example.com/form',
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'depends_on_step_order' => 2,
                    'page_url' => 'https://example.com/one',
                    'form_type' => 'target',
                    'form_fields' => [],
                ],
                [
                    'step_order' => 2,
                    'depends_on_step_order' => 1,
                    'page_url' => 'https://example.com/two',
                    'form_type' => 'target',
                    'form_fields' => [],
                ],
            ],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['form_definitions']);
    }

    public function test_create_task_rejects_missing_dependency_reference(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Missing Dependency Task',
            'target_url' => 'https://example.com/form',
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'depends_on_step_order' => null,
                    'page_url' => 'https://example.com/one',
                    'form_type' => 'target',
                    'form_fields' => [],
                ],
                [
                    'step_order' => 2,
                    'depends_on_step_order' => 99,
                    'page_url' => 'https://example.com/two',
                    'form_type' => 'target',
                    'form_fields' => [],
                ],
            ],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['form_definitions.1.depends_on_step_order']);
    }

    public function test_create_task_ignores_legacy_form_definition_keys(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Legacy Keys Task',
            'target_url' => 'https://example.com/form',
            'form_definitions' => [[
                'step_order' => 1,
                'page_url' => 'https://example.com/form',
                'form_type' => 'target',
                'form_selector' => '#legacy-form',
                'submit_selector' => '#submit',
                'ai_confidence' => 0.99,
                'captcha_detected' => true,
                'two_factor_expected' => true,
                'form_fields' => [[
                    'field_name' => 'email',
                    'field_type' => 'email',
                    'field_selector' => '#email',
                    'sort_order' => 0,
                    'source' => 'legacy-ui',
                ]],
            ]],
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.name', 'Legacy Keys Task')
            ->assertJsonPath('data.form_definitions.0.form_selector', '#legacy-form')
            ->assertJsonCount(1, 'data.form_definitions.0.form_fields');

        $this->assertDatabaseHas('form_definitions', [
            'task_id' => $response->json('data.id'),
            'form_type' => 'target',
            'form_selector' => '#legacy-form',
        ]);
    }

    public function test_create_task_validation_errors(): void
    {
        // Missing required fields
        $response = $this->postJson('/api/tasks', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['name', 'target_url']);
    }

    public function test_create_task_fails_with_invalid_url(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Bad Task',
            'target_url' => 'not-a-url',
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['target_url']);
    }

    public function test_create_task_fails_with_invalid_schedule_type(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Bad Task',
            'target_url' => 'https://example.com',
            'schedule_type' => 'invalid',
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['schedule_type']);
    }

    public function test_create_task_fails_with_max_retries_out_of_range(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Bad Task',
            'target_url' => 'https://example.com',
            'max_retries' => 999,
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['max_retries']);
    }

    // -----------------------------------------------------------------
    // Get single task
    // -----------------------------------------------------------------

    public function test_get_single_task_with_relations(): void
    {
        $task = $this->createTaskWithFormDefinitions();

        $response = $this->getJson("/api/tasks/{$task->id}");

        $response->assertStatus(200)
            ->assertJsonPath('data.id', $task->id)
            ->assertJsonPath('data.name', 'Test Task')
            ->assertJsonStructure([
                'data' => [
                    'id', 'user_id', 'name', 'target_url',
                    'schedule_type', 'status', 'form_definitions',
                    'created_at', 'updated_at',
                ],
            ])
            ->assertJsonCount(1, 'data.form_definitions')
            ->assertJsonCount(2, 'data.form_definitions.0.form_fields');
    }

    public function test_get_nonexistent_task_returns_404(): void
    {
        $fakeId = '00000000-0000-0000-0000-000000000000';
        $response = $this->getJson("/api/tasks/{$fakeId}");

        $response->assertStatus(404);
    }

    // -----------------------------------------------------------------
    // Update task
    // -----------------------------------------------------------------

    public function test_update_task(): void
    {
        $task = $this->createTask();

        $response = $this->putJson("/api/tasks/{$task->id}", [
            'name' => 'Updated Task Name',
            'target_url' => 'https://updated.com/form',
            'max_retries' => 5,
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('data.name', 'Updated Task Name')
            ->assertJsonPath('data.target_url', 'https://updated.com/form')
            ->assertJsonPath('data.max_retries', 5);

        $this->assertDatabaseHas('tasks', [
            'id' => $task->id,
            'name' => 'Updated Task Name',
        ]);
    }

    public function test_update_task_replaces_form_definitions(): void
    {
        $task = $this->createTaskWithFormDefinitions();
        $oldFdId = $task->formDefinitions()->first()->id;

        $response = $this->putJson("/api/tasks/{$task->id}", [
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'page_url' => 'https://example.com/new-page',
                    'form_type' => 'target',
                    'form_selector' => '#new-form',
                    'submit_selector' => '#new-submit',
                    'form_fields' => [
                        [
                            'field_name' => 'new_field',
                            'field_type' => 'text',
                            'field_selector' => '#new-field',
                            'is_required' => true,
                            'sort_order' => 0,
                        ],
                    ],
                ],
            ],
        ]);

        $response->assertStatus(200)
            ->assertJsonCount(1, 'data.form_definitions')
            ->assertJsonPath('data.form_definitions.0.form_type', 'target')
            ->assertJsonCount(1, 'data.form_definitions.0.form_fields')
            ->assertJsonPath('data.form_definitions.0.form_fields.0.field_name', 'new_field');

        // The old form definition should be deleted
        $this->assertDatabaseMissing('form_definitions', ['id' => $oldFdId]);
    }

    public function test_update_task_ignores_legacy_form_definition_keys(): void
    {
        $task = $this->createTask();

        $response = $this->putJson("/api/tasks/{$task->id}", [
            'form_definitions' => [[
                'step_order' => 1,
                'page_url' => 'https://example.com/updated',
                'form_type' => 'target',
                'form_selector' => '#updated-form',
                'submit_selector' => '#updated-submit',
                'ai_confidence' => 0.75,
                'captcha_detected' => false,
                'two_factor_expected' => false,
                'form_fields' => [[
                    'field_name' => 'updated_email',
                    'field_type' => 'email',
                    'field_selector' => '#updated-email',
                    'sort_order' => 0,
                ]],
            ]],
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('data.form_definitions.0.form_selector', '#updated-form')
            ->assertJsonCount(1, 'data.form_definitions.0.form_fields');

        $this->assertDatabaseHas('form_definitions', [
            'task_id' => $task->id,
            'form_selector' => '#updated-form',
        ]);
    }

    // -----------------------------------------------------------------
    // Delete task
    // -----------------------------------------------------------------

    public function test_delete_task(): void
    {
        $task = $this->createTaskWithFormDefinitions();
        $taskId = $task->id;
        $fdId = $task->formDefinitions()->first()->id;

        $response = $this->deleteJson("/api/tasks/{$taskId}");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Task deleted successfully.');

        $this->assertDatabaseMissing('tasks', ['id' => $taskId]);
        // Cascade deletes form definitions
        $this->assertDatabaseMissing('form_definitions', ['id' => $fdId]);
    }

    // -----------------------------------------------------------------
    // Activate task
    // -----------------------------------------------------------------

    public function test_activate_task(): void
    {
        Event::fake([TaskStatusChanged::class]);

        $task = $this->createTask(['status' => 'draft']);

        $response = $this->postJson("/api/tasks/{$task->id}/activate");

        $response->assertStatus(200)
            ->assertJsonPath('data.status', 'active');

        $this->assertDatabaseHas('tasks', [
            'id' => $task->id,
            'status' => 'active',
        ]);

        Event::assertDispatched(TaskStatusChanged::class, function ($event) use ($task) {
            return $event->task->id === $task->id;
        });
    }

    // -----------------------------------------------------------------
    // Pause task
    // -----------------------------------------------------------------

    public function test_pause_task(): void
    {
        Event::fake([TaskStatusChanged::class]);

        $task = $this->createTask(['status' => 'active']);

        $response = $this->postJson("/api/tasks/{$task->id}/pause");

        $response->assertStatus(200)
            ->assertJsonPath('data.status', 'paused');

        $this->assertDatabaseHas('tasks', [
            'id' => $task->id,
            'status' => 'paused',
        ]);

        Event::assertDispatched(TaskStatusChanged::class, function ($event) use ($task) {
            return $event->task->id === $task->id;
        });
    }

    // -----------------------------------------------------------------
    // Execute task
    // -----------------------------------------------------------------

    public function test_execute_task_dispatches_job(): void
    {
        Queue::fake();

        $task = $this->createTask(['status' => 'active']);

        $response = $this->postJson("/api/tasks/{$task->id}/execute");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Task execution queued.');

        Queue::assertPushed(ExecuteTaskJob::class, function ($job) use ($task) {
            return $job->task->id === $task->id && $job->isDryRun === false;
        });
    }

    // -----------------------------------------------------------------
    // Dry-run task
    // -----------------------------------------------------------------

    public function test_dry_run_task_dispatches_job_with_dry_run_flag(): void
    {
        Queue::fake();

        $task = $this->createTask();

        $response = $this->postJson("/api/tasks/{$task->id}/dry-run");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Dry run execution queued.');

        Queue::assertPushed(ExecuteTaskJob::class, function ($job) use ($task) {
            return $job->task->id === $task->id && $job->isDryRun === true;
        });
    }

    // -----------------------------------------------------------------
    // Clone task
    // -----------------------------------------------------------------

    public function test_clone_task(): void
    {
        $task = $this->createTaskWithFormDefinitions();

        $response = $this->postJson("/api/tasks/{$task->id}/clone");

        $response->assertStatus(201);

        $cloned = $response->json('data');

        // The clone should have a different ID
        $this->assertNotEquals($task->id, $cloned['id']);

        // The clone should have the original task name with " (Copy)" appended
        $this->assertEquals('Test Task (Copy)', $cloned['name']);

        // Status should be reset to draft
        $this->assertEquals('draft', $cloned['status']);

        // Should reference the original task
        $this->assertEquals($task->id, $cloned['cloned_from']);

        // Form definitions should be cloned
        $this->assertCount(1, $cloned['form_definitions']);
        $this->assertCount(2, $cloned['form_definitions'][0]['form_fields']);

        // Sensitive field values should be cleared in the clone
        $clonedFields = $cloned['form_definitions'][0]['form_fields'];
        $passwordField = collect($clonedFields)->firstWhere('field_name', 'password');
        $this->assertTrue($passwordField['is_sensitive']);
        // The API masks sensitive values with '********' even when null in DB
        $this->assertEquals('********', $passwordField['preset_value']);
        // Verify the actual DB value was cleared
        $dbField = FormField::where('form_definition_id', $cloned['form_definitions'][0]['id'])
            ->where('field_name', 'password')
            ->first();
        $this->assertNull($dbField->preset_value);

        // Non-sensitive field values should be preserved
        $usernameField = collect($clonedFields)->firstWhere('field_name', 'username');
        $this->assertFalse($usernameField['is_sensitive']);
        $this->assertEquals('testuser', $usernameField['preset_value']);

        // Verify the clone was saved to the database
        $this->assertDatabaseHas('tasks', [
            'id' => $cloned['id'],
            'name' => 'Test Task (Copy)',
            'cloned_from' => $task->id,
        ]);
    }

    // -----------------------------------------------------------------
    // Authorization
    // -----------------------------------------------------------------

    public function test_user_cannot_access_another_users_task(): void
    {
        $otherUser = User::create([
            'name' => 'Other User',
            'email' => 'other@example.com',
            'password' => bcrypt('password123'),
        ]);

        $otherTask = Task::create([
            'user_id' => $otherUser->id,
            'name' => 'Other Task',
            'target_url' => 'https://other.com',
            'status' => 'draft',
        ]);

        // Attempt to view
        $this->getJson("/api/tasks/{$otherTask->id}")->assertStatus(403);

        // Attempt to update
        $this->putJson("/api/tasks/{$otherTask->id}", [
            'name' => 'Hacked',
        ])->assertStatus(403);

        // Attempt to delete
        $this->deleteJson("/api/tasks/{$otherTask->id}")->assertStatus(403);

        // Attempt to activate
        $this->postJson("/api/tasks/{$otherTask->id}/activate")->assertStatus(403);

        // Attempt to pause
        $this->postJson("/api/tasks/{$otherTask->id}/pause")->assertStatus(403);

        // Attempt to execute
        $this->postJson("/api/tasks/{$otherTask->id}/execute")->assertStatus(403);

        // Attempt to dry-run
        $this->postJson("/api/tasks/{$otherTask->id}/dry-run")->assertStatus(403);

        // Attempt to clone
        $this->postJson("/api/tasks/{$otherTask->id}/clone")->assertStatus(403);
    }

    // -----------------------------------------------------------------
    // Export (via TaskController)
    // -----------------------------------------------------------------

    public function test_export_task_excludes_sensitive_values_and_internal_fields(): void
    {
        $task = $this->createTaskWithFormDefinitions();

        $response = $this->postJson("/api/tasks/{$task->id}/export");

        $response->assertStatus(200);

        $data = $response->json();

        // Internal fields should be removed
        $this->assertArrayNotHasKey('id', $data);
        $this->assertArrayNotHasKey('user_id', $data);
        $this->assertArrayNotHasKey('created_at', $data);
        $this->assertArrayNotHasKey('updated_at', $data);

        // Task data should be present
        $this->assertEquals('Test Task', $data['name']);
        $this->assertEquals('https://example.com/form', $data['target_url']);

        // Sensitive field values should be nullified
        $passwordField = collect($data['form_definitions'][0]['form_fields'])
            ->firstWhere('is_sensitive', true);
        $this->assertNull($passwordField['preset_value']);
    }

    // -----------------------------------------------------------------
    // Import (via TaskController)
    // -----------------------------------------------------------------

    public function test_import_task_from_json(): void
    {
        $response = $this->postJson('/api/tasks/import', [
            'name' => 'Imported Task',
            'target_url' => 'https://import.com/form',
            'form_definitions' => [
                [
                    'step_order' => 1,
                    'page_url' => 'https://import.com/login',
                    'form_type' => 'login',
                    'form_selector' => '#form',
                    'submit_selector' => '#submit',
                    'form_fields' => [
                        [
                            'field_name' => 'email',
                            'field_type' => 'email',
                            'field_selector' => '#email',
                            'sort_order' => 0,
                        ],
                    ],
                ],
            ],
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.name', 'Imported Task')
            ->assertJsonPath('data.status', 'draft')
            ->assertJsonPath('data.user_id', $this->user->id)
            ->assertJsonCount(1, 'data.form_definitions')
            ->assertJsonCount(1, 'data.form_definitions.0.form_fields');

        $this->assertDatabaseHas('tasks', [
            'name' => 'Imported Task',
            'status' => 'draft',
            'user_id' => $this->user->id,
        ]);
    }

    public function test_import_task_ignores_legacy_form_definition_keys(): void
    {
        $response = $this->postJson('/api/tasks/import', [
            'name' => 'Imported Legacy Task',
            'target_url' => 'https://import.com/form',
            'form_definitions' => [[
                'step_order' => 1,
                'page_url' => 'https://import.com/form',
                'form_type' => 'target',
                'form_selector' => '#import-legacy-form',
                'submit_selector' => '#submit',
                'ai_confidence' => 0.84,
                'captcha_detected' => false,
                'two_factor_expected' => false,
                'form_fields' => [[
                    'field_name' => 'email',
                    'field_type' => 'email',
                    'field_selector' => '#email',
                    'sort_order' => 0,
                ]],
            ]],
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.name', 'Imported Legacy Task')
            ->assertJsonPath('data.form_definitions.0.form_selector', '#import-legacy-form')
            ->assertJsonCount(1, 'data.form_definitions.0.form_fields');

        $this->assertDatabaseHas('form_definitions', [
            'task_id' => $response->json('data.id'),
            'form_selector' => '#import-legacy-form',
            'form_type' => 'target',
        ]);
    }
}
