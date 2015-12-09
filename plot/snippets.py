# terminal "pdf colour enhanced"
# terminal "png truecolor butt"
plotOutputPrologue="""
reset
set terminal {terminal}
set output "{fname}"
"""
plotOutputEpilogue="""
set output "delete.me"
"""

plotPalette="""
# SETTING STYLES
set style line 100 lt 3 lc rgb '#000000' lw 1 #black
set style line 101 lt 3 lc rgb '#902020' lw 2 #red
set style line 102 lt 3 lc rgb '#E07000' lw 2 #orange
set style line 103 lt 3 lc rgb '#F0A010' lw 2 #yellow
set style line 104 lt 3 lc rgb '#209020' lw 2 #green
set style line 105 lt 3 lc rgb '#90C0C0' lw 2 #water
set style line 106 lt 3 lc rgb '#203090' lw 2 #blue
set style line 107 lt 3 lc rgb '#808080' lw 2 #gray
set style line 109 lt 3 lc rgb '#702020' lw 3 #darkRed
set style line 110 lt 3 lc rgb '#808010' lw 3 #darkYellow
set style fill solid .90 border lt -1
set style rect fc lt -1 fs solid 0.15 noborder
set style arrow 1 head nofilled size screen 0.03,15 ls 109
set style arrow 2 head nofilled size screen 0.03,15 ls 110
set boxwidth 0.8 absolute
set bar .5
"""
plotFrameVertical="""
# SETTING VERTICAL FRAME
set border 3 front ls 107
set tics nomirror out scale 0.75
set format '%g'
set grid noxtics ytics
"""
plotFrameHorizontal="""
# SETTING HORIZONTAL FRAME
set border 9 front ls 107
set format '%g'
set grid noxtics noytics y2tics
unset ytics
unset y2tics
set xtic rotate right nomirror out scale .75
set xrange [-1.5:]
set y2tics rotate by 90 nomirror out scale .75
set y2range [0:{ymax}]
set size 1, 1
set key outside top horizontal Right noreverse noenhanced autotitle nobox
set ylabel "{ylabel}"
"""
plotTaskBackground="""
# Task WCET + Period
set obj rect from graph 1, second 0 to graph 0, second {WCET} behind fc rgb'#902020' fs solid .4
set obj rect from graph 1, second {WCET} to graph 0, second {Period} behind fc rgb'#F0A010' fs solid .4
set arrow 1 from -1, second ({ArrowLength}) to -1, second 0 as 1
set arrow 2 from -1, second ({WCET}-{ArrowLength}) to -1, second {WCET} as 1
set arrow 3 from -1, second ({Period}-{ArrowLength}) to -1, second {Period} as 2
set label "WCET" at -1, second ({WCET}-{ArrowLength}-{shift}) right rotate by 90 tc rgb'#702020'
set label "Period" at -1, second ({Period}-{ArrowLength}-{shift}) right rotate by 90 tc rgb'#809010'
"""
plotWordsVertical ="""
# SETTING HUMAN-READABLE INFO
set key inside {position} {orientation} Right noreverse noenhanced autotitle nobox
set title "{title}"
set xlabel "{xlabel}"
set ylabel "{ylabel}"
set yrange [-.1:{ymax}]
"""
plotClusteredHistogram="""
# PLOT TYPE
set style histogram clustered gap 3 title textcolor lt -1
set style data histograms
"""
plotErrorbarHistogram="""
# PLOT TYPE
set style histogram errorbars gap 3 lw 2
set style data histograms
"""

html="""
<html>
<head>
<title>Automate: Experiment Results</title>
<style>
table tr:nth-child(even) {{
    background-color: #eee;
}}
table tr:nth-child(odd) {{
    background-color: #fff;
}}
table th {{
    color: #eee;
    background-color: #666;
}}
table {{
  width: 50%;
  margin: 1em auto 0 auto;
}}
.all {{
  margin: 3%;
  background-color: #ddd;
}}
.title {{
  width: 90%;
  background-color: #333;
  color: #EC3;
  padding: 5px 5% 5px 5%;
  text-align: center;
  border-radius: 5px;
}}
.chapter {{
  width: 98%;
  background-color: #666;
  color: #EC3;
  padding: 5px 1% 5px 1%;
  margin: 0;
  text-align: left;
  border-radius: 5px;
}}
.section {{
  color: #333;
  margin-top: 1em;
  margin-bottom: 5px;
}}
.info {{
  border-radius: 5px;
  background-color: #fff;
  padding: 5px 1% 5px 1%;
  margin: 0;
  color: #222;
}}
.blob {{
  border-radius: 5px;
  background-color: #ccc;
  padding: 5px 5px 5px 5px;
  margin-top: 10px;
  color: #222;
}}
.centerchart {{
  width: 100%;
  margin: 0 auto;
  text-align: center;
}}
.chart {{
  display: inline-block;
  margin-left: auto;
  margin-right: auto;
}}
.task {{
  width:100%;
  background-color: #fff;
  border-radius: 5px;
  margin: 1em auto 0 auto;
  text-align: center;
}}
</style>
</head>
<body class="all">
<h1 class="title">Experiment Results</h1>
<ul class="menu">
  <li><a href="#system-info">system info</a></li>
  <li><a href="#system-overhead">system overheads</a>
    <ol>
      <li><a href="#system-overhead1">deadline misses</a></li>
      <li><a href="#system-overhead2">scheduler overhead</a></li>
      <li><a href="#system-overhead3">release latency</a></li>
      <li><a href="#system-overhead4">context-switches overhead</a></li>
      <li><a href="#system-overhead5">preemptions count</a></li>
      <li><a href="#system-overhead6">migrations count</a></li>
    </ol>
  </li>
  <li><a href="#task-statistics">task statistics</a></li>
</ul>

<div id="system-info" class="blob">
<h2 class="chapter">System Info</h2>
<h3 class="section">System</h3>
<div class="info">
  <p>The data was produced using the following system setup:</p>
  <ul>
    <li>CPUs: {cpuCount}</li>
    <li>Tasks: {taskCount}</li>
    <li>Duration: {duration} sec</li>
  </ul>
</div>

<h3 class="section">Task set</h3>
<div class="info">
  <p>The task set used is reported below. For each task it is defined its name,
     its WCET and its period.<p>
  <table>
  <tr><th>Task ID</th><th>WCET</th><th>Period</th></tr>
  {taskTable}
  </table>
</div>
</div>


<div id="system-overhead" class="blob">
<h2 class="chapter">System Overhead</h2>
<p>Results are given on a per-CPU basis and on a system-wide base.
   <em>per-CPU basis</em> is useful to understand how the overhead is
   distributed inside the platform. <em>system-wide base</em> is useful to
   perform general comparisons of the schedulers.</p>

<h3 id="system-overhead1" class="section">Deadline Misses</h3>
<div class="info">
  <p>The <em>deadline misses</em> shows how many time during the whole
     experiment a task fails to meet its deadline.</p>
  <div class="centerchart">
    <img class="chart" src="{plotFolder}/Chart5system.png" />
  </div>
</div>

<h3 id="system-overhead2" class="section">Scheduler Overhead</h3>
<div class="info">
  <p>The <em>scheduler overhead</em> contains the overhead produced by the
     scheduling operations of the specified scheduler (i.e., manage a newly
     released task, deciding which task must execute, modifying the kernel such
     that the correct task will execute).</p>
  <div class="centerchart">
      <img class="chart" src="{plotFolder}/Chart0perCPU.png" />
      <img class="chart" src="{plotFolder}/Chart0system.png" />
  </div>
</div>

<h3 id="system-overhead3" class="section">Release Latency</h3>
<div class="info">
  <p>The <em>release latency</em> shows how responsive is the kernel. We shows
     only the max observed values.</p>
  <div class="centerchart">
    <img class="chart" src="{plotFolder}/Chart2perCPU.png" />
    <img class="chart" src="{plotFolder}/Chart2system.png" />
  </div>
</div>

<h3 id="system-overhead4" class="section">Context-Switch Overhead</h3>
<div class="info">
  <p>The <em>context-switch overhead</em> contains the overhead produced by
     the scheduler while changing the context between one task to another. The
     charts show the cumulative time spent in changing the context during the
     whole experiment. These values are related to the number of
     preemptions.</p>
  <div class="centerchart">
    <img class="chart" src="{plotFolder}/Chart1perCPU.png" />
    <img class="chart" src="{plotFolder}/Chart1system.png" />
  </div>
</div>

<h3 id="system-overhead5" class="section">Preemptions Count</h3>
<div class="info">
  <p>The <em>preemptions count</em> shows how many times the scheduler needs
     to change context between tasks. These values are related to the
     context-switch overhead.</p>
  <div class="centerchart">
    <img class="chart" src="{plotFolder}/Chart3perCPU.png" />
    <img class="chart" src="{plotFolder}/Chart3system.png" />
  </div>
</div>

<h3 id="system-overhead6" class="section">Migrations Count</h3>
<div class="info">
  </p>The <em>migrations count</em> shows how many times the scheduler decided
      to migrate one task from one cpu to another. We consider only
      <strong>JOB LEVEL MIGRATION????</strong>.</p>
  <div class="centerchart">
    <img class="chart" src="{plotFolder}/Chart4system.png" />
  </div>
</div>
</div>

<div id="task-statistics" class="blob">
<h2 class="chapter">Task Statistics</h2>
<p>For each task in the system we shows: </p>
<ol>
  <li>its response time, computed as the time span between the first executed
      instruction of a job to the last executed instruction of the job. NB: we
      are not considering the response time of a task as the time span between
      its release time to its completion time.</li>
  <li>its jitter, computed as the time span between the time instant in which
      a job is released to the time instant the same job executes its first
      instruction.</li>
</ol>
<p>For each of these items we show the average value (computed as the average
   of all the jobs of the task) and the min and max value ever observed of any
   of its job.</p>

{taskStats}
</div>
</body>
</html>
"""