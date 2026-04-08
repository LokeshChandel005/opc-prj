import statistics
import heapq
import pandas as pd
import matplotlib.pyplot as plt

processing_times = [6, 3, 4.5, 2.5]
WIP_LIMIT = 20
weekly_demand = [380, 412, 399, 425, 393, 385, 405, 370]
WEEK_MINUTES = 2400
PLANNING_OFFSET = WEEK_MINUTES

def generate_customer_orders(weekly_demand, week_minutes):
    jobs = []
    job_id = 1
    for week_idx, demand in enumerate(weekly_demand):
        demand_time = week_idx * week_minutes
        due_date = (week_idx + 1) * week_minutes
        planned_release_time = max(0, demand_time - PLANNING_OFFSET)
        for _ in range(demand):
            jobs.append({
                "job_id": job_id,
                "week": week_idx + 1,
                "demand_time": demand_time,
                "due_date": due_date,
                "planned_release_time": planned_release_time
            })
            job_id += 1
    return jobs

def process_job_through_line(release_time, machine_available_times, processing_times):
    current_time = release_time
    for i, p_time in enumerate(processing_times):
        start_time = max(current_time, machine_available_times[i])
        finish_time = start_time + p_time
        machine_available_times[i] = finish_time
        current_time = finish_time
    completion_time = current_time
    lead_time = completion_time - release_time
    return completion_time, lead_time

def compute_average_wip(results):
    events = []
    for r in results:
        events.append((r["release_time"], +1))
        events.append((r["completion_time"], -1))
    events.sort(key=lambda x: (x[0], x[1]))
    wip = 0
    area = 0
    prev_time = events[0][0]
    for time, change in events:
        duration = time - prev_time
        area += wip * duration
        wip += change
        prev_time = time
    total_time = max(r["completion_time"] for r in results) - min(r["release_time"] for r in results)
    return area / total_time if total_time > 0 else 0

def simulate_mrp(jobs, processing_times):
    machine_available_times = [0] * len(processing_times)
    results = []
    jobs_sorted = sorted(jobs, key=lambda j: (j["planned_release_time"], j["job_id"]))
    for job in jobs_sorted:
        release_time = job["planned_release_time"]
        completion_time, lead_time = process_job_through_line(
            release_time, machine_available_times, processing_times
        )
        results.append({
            "job_id": job["job_id"],
            "system": "MRP",
            "week": job["week"],
            "release_time": release_time,
            "completion_time": completion_time,
            "lead_time": lead_time,
            "due_date": job["due_date"],
            "late": 1 if completion_time > job["due_date"] else 0
        })
    return results

def simulate_wip_capped_system(jobs, processing_times, wip_limit, availability_key, system_name):
    machine_available_times = [0] * len(processing_times)
    results = []
    jobs_sorted = sorted(jobs, key=lambda j: (j[availability_key], j["job_id"]))
    active_jobs_heap = []
    for job in jobs_sorted:
        eligible_time = job[availability_key]
        while active_jobs_heap and active_jobs_heap[0] <= eligible_time:
            heapq.heappop(active_jobs_heap)
        if len(active_jobs_heap) < wip_limit:
            release_time = eligible_time
        else:
            earliest_completion = heapq.heappop(active_jobs_heap)
            release_time = earliest_completion
            while active_jobs_heap and active_jobs_heap[0] <= release_time:
                heapq.heappop(active_jobs_heap)
        completion_time, lead_time = process_job_through_line(
            release_time, machine_available_times, processing_times
        )
        heapq.heappush(active_jobs_heap, completion_time)
        results.append({
            "job_id": job["job_id"],
            "system": system_name,
            "week": job["week"],
            "release_time": release_time,
            "completion_time": completion_time,
            "lead_time": lead_time,
            "due_date": job["due_date"],
            "late": 1 if completion_time > job["due_date"] else 0
        })
    return results

def simulate_conwip(jobs, processing_times, wip_limit):
    return simulate_wip_capped_system(
        jobs=jobs,
        processing_times=processing_times,
        wip_limit=wip_limit,
        availability_key="demand_time",
        system_name="CONWIP"
    )

def simulate_hybrid(jobs, processing_times, wip_limit):
    return simulate_wip_capped_system(
        jobs=jobs,
        processing_times=processing_times,
        wip_limit=wip_limit,
        availability_key="planned_release_time",
        system_name="Hybrid"
    )

def calculate_metrics(results):
    total_jobs = len(results)
    avg_lead_time = statistics.mean(r["lead_time"] for r in results)
    late_jobs = sum(r["late"] for r in results)
    late_pct = (late_jobs / total_jobs) * 100
    avg_wip = compute_average_wip(results)
    first_release = min(r["release_time"] for r in results)
    last_completion = max(r["completion_time"] for r in results)
    total_time = last_completion - first_release
    throughput_rate = total_jobs / total_time if total_time > 0 else 0
    return {
        "Throughput (jobs)": total_jobs,
        "Throughput Rate (jobs/min)": round(throughput_rate, 4),
        "Avg Lead Time (min)": round(avg_lead_time, 2),
        "Late Jobs": late_jobs,
        "Late Jobs (%)": round(late_pct, 2),
        "Avg WIP": round(avg_wip, 2)
    }

jobs = generate_customer_orders(weekly_demand, WEEK_MINUTES)

mrp_results = simulate_mrp(jobs, processing_times)
conwip_results = simulate_conwip(jobs, processing_times, WIP_LIMIT)
hybrid_results = simulate_hybrid(jobs, processing_times, WIP_LIMIT)

mrp_metrics = calculate_metrics(mrp_results)
conwip_metrics = calculate_metrics(conwip_results)
hybrid_metrics = calculate_metrics(hybrid_results)

summary_df = pd.DataFrame([
    {"System": "MRP", **mrp_metrics},
    {"System": "CONWIP", **conwip_metrics},
    {"System": "Hybrid", **hybrid_metrics}
])

print("\n=== PERFORMANCE COMPARISON ===\n")
print(summary_df.to_string(index=False))

summary_df.to_csv("summary_results.csv", index=False)

all_results_df = pd.DataFrame(mrp_results + conwip_results + hybrid_results)
all_results_df.to_csv("desk_fan_body_simulation_results.csv", index=False)

print("\nSummary results saved to: summary_results.csv")
print("Detailed job-wise results saved to: desk_fan_body_simulation_results.csv")

late_by_week = all_results_df.groupby(["system", "week"])["late"].sum().reset_index()

print("\n=== LATE JOBS BY WEEK ===\n")
print(late_by_week.to_string(index=False))

plt.figure(figsize=(8, 5))
plt.bar(summary_df["System"], summary_df["Avg WIP"])
plt.title("Avg WIP")
plt.xlabel("Production Control Policy")
plt.ylabel("Average WIP")
plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()

plt.figure(figsize=(8, 5))
plt.bar(summary_df["System"], summary_df["Avg Lead Time (min)"])
plt.title("Avg Lead Time (min)")
plt.xlabel("Production Control Policy")
plt.ylabel("Avg Lead Time (min)")
plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()

plt.figure(figsize=(8, 5))
plt.bar(summary_df["System"], summary_df["Late Jobs (%)"])
plt.title("Late Jobs (%)")
plt.xlabel("Production Control Policy")
plt.ylabel("Late Jobs (%)")
plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()

plt.figure(figsize=(8, 5))
plt.bar(summary_df["System"], summary_df["Throughput Rate (jobs/min)"])
plt.title("Throughput Rate (jobs/min)")
plt.xlabel("Production Control Policy")
plt.ylabel("Throughput Rate (jobs/min)")
plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()