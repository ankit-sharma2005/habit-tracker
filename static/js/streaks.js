/* streaks.js
   ==========
   Draws the two Chart.js graphs on the streak page:

   a) a bar chart of "completed / not completed" per day for the last 7 or 30
      days, with a line showing the running total in that window,
   b) a doughnut chart of overall completion for the selected habit.

   The numbers come from GET /streaks/chart-data (streaks.py -> stats.py),
   so the browser never calculates anything itself - it only draws.

   When the 7/30-day dropdown changes we fetch the same endpoint again and
   replace the charts, without reloading the page. */

(function () {
  "use strict";

  var page = document.getElementById("streak-page");
  if (!page || typeof Chart === "undefined") {
    return; // not the streak page, or the Chart.js file did not load
  }

  var habitId = page.dataset.habitId;
  var chartUrl = page.dataset.chartUrl;
  var rangeSelect = document.getElementById("chart-range");
  var summaryText = document.getElementById("chart-summary");
  var doughnutCaption = document.getElementById("doughnut-caption");

  // Chart instances are kept so they can be destroyed before redrawing;
  // without this the old chart stays behind the new one.
  var completionsChart = null;
  var doughnutChart = null;

  var COLORS = {
    green: "#22c55e",
    greenSoft: "rgba(34, 197, 94, 0.35)",
    line: "#4f46e5",
    grey: "#e2e8f0"
  };

  function loadCharts(days) {
    return fetch(chartUrl + "?habit_id=" + encodeURIComponent(habitId) + "&days=" + days, {
      headers: { Accept: "application/json" }
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Could not load chart data (" + response.status + ").");
        }
        return response.json();
      })
      .then(function (data) {
        drawCompletions(data);
        drawDoughnut(data);
      });
  }

  // -- a) completions per day ---------------------------------------------
  function drawCompletions(data) {
    var canvas = document.getElementById("completionsChart");
    if (completionsChart) {
      completionsChart.destroy();
    }

    completionsChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Completed",
            data: data.completed,
            backgroundColor: COLORS.greenSoft,
            borderColor: COLORS.green,
            borderWidth: 1,
            borderRadius: 4,
            maxBarThickness: 28,
            yAxisID: "y"
          },
          {
            type: "line",
            label: "Total in this window",
            data: data.cumulative,
            borderColor: COLORS.line,
            backgroundColor: COLORS.line,
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 2,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          y: {
            beginAtZero: true,
            suggestedMax: 1,
            ticks: { stepSize: 1, precision: 0 },
            title: { display: true, text: "Done?" }
          },
          y1: {
            beginAtZero: true,
            position: "right",
            grid: { drawOnChartArea: false },
            title: { display: true, text: "Total" }
          }
        },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12 } },
          tooltip: {
            callbacks: {
              label: function (item) {
                if (item.dataset.yAxisID === "y") {
                  return item.parsed.y === 1 ? "Completed" : "Missed";
                }
                return "Total so far: " + item.parsed.y;
              }
            }
          }
        }
      }
    });

    var done = data.completed.reduce(function (total, value) {
      return total + value;
    }, 0);

    if (summaryText) {
      summaryText.textContent = done + " of the last " + data.days + " days completed.";
    }
  }

  // -- b) overall completion doughnut -------------------------------------
  function drawDoughnut(data) {
    var canvas = document.getElementById("completionChart");
    if (doughnutChart) {
      doughnutChart.destroy();
    }

    var stats = data.doughnut;

    doughnutChart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Completed", "Missed"],
        datasets: [
          {
            data: [stats.completed, Math.max(0, stats.missed)],
            backgroundColor: [COLORS.green, COLORS.grey],
            borderWidth: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "64%",
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12 } },
          tooltip: {
            callbacks: {
              label: function (item) {
                return item.label + ": " + item.parsed + " day(s)";
              }
            }
          }
        }
      }
    });

    if (doughnutCaption) {
      doughnutCaption.textContent =
        stats.percent + "% overall · " + stats.completed + " of " + stats.possible + " possible days";
    }
  }

  function showError(error) {
    if (summaryText) {
      summaryText.textContent = error.message;
    }
  }

  // -- start ---------------------------------------------------------------
  if (rangeSelect) {
    rangeSelect.addEventListener("change", function () {
      loadCharts(rangeSelect.value).catch(showError);
    });
  }

  loadCharts(rangeSelect ? rangeSelect.value : 7).catch(showError);
})();
