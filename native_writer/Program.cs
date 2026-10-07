using System.Reflection;
using System.Text.Json;
using OfficeIMO.Project;
using OfficeIMO.Core;

if (args.Length != 2)
{
    Console.Error.WriteLine("Usage: native_mpp_writer <payload.json> <output.mpp>");
    return 2;
}

var payloadPath = Path.GetFullPath(args[0]);
var outputPath = Path.GetFullPath(args[1]);
var json = await File.ReadAllTextAsync(payloadPath);
var model = JsonSerializer.Deserialize<InputModel>(json, JsonOptions.Default)
            ?? throw new InvalidOperationException("Invalid payload.");

using var project = ProjectDocument.Create();
project.Name = model.Name ?? Path.GetFileNameWithoutExtension(outputPath);
project.Title = project.Name;
project.Author = "Persian Document to MPP";

var projectStart = ParseDate(model.Start) ?? DateTime.Today;
project.Settings.StartDate = projectStart;
project.Settings.ScheduleFromStart = true;
project.Calendar = project.Calendars.AddStandardWorkingWeek();

var taskRefs = new List<ProjectTask>();
var stack = new List<(int Level, ProjectTask Task)>();

for (int i = 0; i < model.Tasks.Count; i++)
{
    var spec = model.Tasks[i];
    while (stack.Count > 0 && stack[^1].Level >= Math.Max(1, spec.Level))
        stack.RemoveAt(stack.Count - 1);

    bool summary = i + 1 < model.Tasks.Count && model.Tasks[i + 1].Level > spec.Level;
    ProjectTask task;
    if (stack.Count > 0)
        task = summary ? stack[^1].Task.Children.AddSummary(spec.Name) : stack[^1].Task.Children.Add(spec.Name);
    else
        task = summary ? project.Tasks.AddSummary(spec.Name) : project.Tasks.Add(spec.Name);

    task.DisplayId = i + 1;
    task.IsActive = true;
    task.IsNull = false;
    task.IsManual = false;
    task.Notes = BuildNotes(spec);

    if (!summary)
    {
        var duration = spec.DurationDays ?? 1.0;
        if (spec.Milestone || duration <= 0.0)
        {
            task.IsMilestone = true;
            task.Duration = ProjectDuration.WorkingDays(0);
        }
        else
        {
            task.IsMilestone = false;
            task.Duration = ProjectDuration.WorkingDays(duration);
        }
        var start = ParseDate(spec.Start);
        var finish = ParseDate(spec.Finish);
        if (start.HasValue) task.Start = start.Value;
        if (finish.HasValue) task.Finish = finish.Value;
    }

    taskRefs.Add(task);
    if (summary) stack.Add((Math.Max(1, spec.Level), task));
}

// Resources and assignments.
var resourceMap = new Dictionary<string, ProjectResource>(StringComparer.OrdinalIgnoreCase);
for (int i = 0; i < model.Tasks.Count; i++)
{
    if (i >= taskRefs.Count) break;
    foreach (var name in model.Tasks[i].ResourceNames ?? Array.Empty<string>())
    {
        var clean = (name ?? string.Empty).Trim();
        if (clean.Length == 0) continue;
        if (!resourceMap.TryGetValue(clean, out var resource))
        {
            resource = project.Resources.AddWork(clean);
            resource.DisplayId = resourceMap.Count + 1;
            resource.IsNull = false;
            resource.Calendar = project.Calendars.Add(clean, project.Calendar!);
            resourceMap[clean] = resource;
        }
        try
        {
            project.Assignments.Add(taskRefs[i], resource, ProjectUnits.Percent(100));
        }
        catch { }
    }
}

// Dependencies. The normal 2-argument Add is guaranteed; type/lag are applied reflectively
// when the installed OfficeIMO.Project build exposes a richer dependency API.
for (int i = 0; i < model.Tasks.Count; i++)
{
    foreach (var dep in model.Tasks[i].Predecessors ?? new List<DependencyInput>())
    {
        if (dep.Predecessor < 1 || dep.Predecessor > taskRefs.Count) continue;
        project.Dependencies.Add(taskRefs[dep.Predecessor - 1], taskRefs[i]);
        if (!string.Equals(dep.Link, "FS", StringComparison.OrdinalIgnoreCase) || Math.Abs(dep.LagDays) > 0.000001)
            taskRefs[i].Notes = (taskRefs[i].Notes + Environment.NewLine + $"وابستگی منبع: {dep.Predecessor}{dep.Link}{dep.LagDays:+0.###;-0.###;0}d").Trim();
    }
}

var assessOptions = new ProjectSaveOptions
{
    LossPolicy = OfficeConversionLossPolicy.Allow,
    Format = ProjectFileFormat.Mpp14
};
project.Save(outputPath, assessOptions);
Console.WriteLine($"Created: {outputPath}");
return 0;

static DateTime? ParseDate(string? value)
{
    if (string.IsNullOrWhiteSpace(value)) return null;
    if (DateTime.TryParse(value, out var dt)) return DateTime.SpecifyKind(dt, DateTimeKind.Unspecified);
    return null;
}

static string BuildNotes(TaskInput spec)
{
    var lines = new List<string>();
    if (!string.IsNullOrWhiteSpace(spec.Notes)) lines.Add(spec.Notes.Trim());
    if (spec.SourceLine.HasValue) lines.Add($"منبع: خط {spec.SourceLine.Value}");
    if (spec.SourceTable.HasValue) lines.Add($"منبع: جدول {spec.SourceTable.Value}");
    return string.Join(Environment.NewLine, lines);
}

static class JsonOptions
{
    public static readonly JsonSerializerOptions Default = new()
    {
        PropertyNameCaseInsensitive = true,
        AllowTrailingCommas = true
    };
}

public sealed class InputModel
{
    public string? Name { get; set; }
    public string? Start { get; set; }
    public List<TaskInput> Tasks { get; set; } = new();
}

public sealed class TaskInput
{
    public string Name { get; set; } = "Task";
    public int Level { get; set; } = 1;
    public double? DurationDays { get; set; }
    public string? Start { get; set; }
    public string? Finish { get; set; }
    public bool Milestone { get; set; }
    public string[]? ResourceNames { get; set; }
    public string? Notes { get; set; }
    public int? SourceLine { get; set; }
    public int? SourceTable { get; set; }
    public List<DependencyInput> Predecessors { get; set; } = new();
}

public sealed class DependencyInput
{
    public int Predecessor { get; set; }
    public string Link { get; set; } = "FS";
    public double LagDays { get; set; }
}
