// vim: set expandtab shiftwidth=4 softtabstop=4:

var vdxplot = function() {
    var columns = { numeric: {}, text:{} };
    var id2index = {}
    var display = [];
    var tooltip_shown = false;
    var action = false;
    var custom_scheme = "vdxplot";
    var sweep_select = false;
    var plot = null;

    function update_columns(new_columns) {
        columns = new_columns;
        text = columns["text"];
        numeric = columns["numeric"];
        id2index = {};
        display = [];
        $.each(text["id"], function(i, id) {
            id2index[id] = i;
            display[i] = false;
        });

        // Clear out the table and fill in with text
        // then numeric column names
        $("#column_table").empty()
            .append($("<col/>"), $("<col/>"))
            .append($("<tr/>").append(
                $("<th>/>").text("Column"),
                $("<th>/>").text("Value")));
        $.each(text, function(r, v) {
            $("#column_table").append($("<tr/>").append(
                                        $("<td/>").text(r),
                                        $("<td/>").addClass("value")
                                                  .prop("title", r)))
        });
        for (var i = 1; i < 3; i++) {
            $("#xaxis" + i).children().remove();
            $("#yaxis" + i).children().remove();
        }
        var labels = [];
        $.each(numeric, function(r, v) {
            $("#column_table").append($("<tr/>").append(
                                        $("<td/>").text(r),
                                        $("<td/>").addClass("value")
                                                  .prop("title", r)));
            labels.push(r);
            for (var i = 1; i < 3; i++) {
                $("#xaxis" + i).append($("<option/>").prop("value", r)
                                                     .text(r));
                $("#yaxis" + i).append($("<option/>").prop("value", r)
                                                     .text(r));
            }
        });
        $("#xaxis1").val(labels[0]);
        $("#yaxis1").val(labels[Math.min(1, labels.length - 1)]);
        $("#xaxis2").val(labels[0]);
        $("#yaxis2").val(labels[Math.min(2, labels.length - 1)]);

        update_plot();
    }

    function update_plot() {
        // Get order of compounds based on sort column
        var series = [];
        for (var i = 1; i < 3; i++)
            if ($("#series" + i).is(":checked"))
                add_series(series, i);

        // Show the data
        plot.setData(series);
        plot.setupGrid();
        plot.draw();
    }

    function add_series(series, i) {
        // Generate a series for each shown column
        var numeric = columns["numeric"];
        var xname = $("#xaxis" + i).find(":selected").text();
        var yname = $("#yaxis" + i).find(":selected").text();
        if (!xname || !yname)
            return;
        var xdata = numeric[xname];
        var ydata = numeric[yname];
        var label = xname + '-' + yname;
        series.push({
            index: i,
            color: i - 1,
            points: { show: true },
            label: label,
            xname: xname,
            yname: yname,
            xaxis: i,
            yaxis: i,
            data:
                xdata.map(function(e, i) {
                    return [e, ydata[i]];
                })
        });
    }

    function plot_click(event, pos, item) {
        if (sweep_select || item == null)
            return;
        var raw_index = item.dataIndex;
        var id = columns["text"]["id"][raw_index];
        window.location = custom_scheme + ":" + action + "?id=" + id;
    }

    function plot_hover(event, pos, item) {
        if (item == null) {
            // Hovering over nothing or histogram bar
            if (tooltip_shown) {
                // Hide tooltip
                $("#tooltip").css( { display: "none" } );
                tooltip_shown = false;
                // But leave table data alone
            }
        } else {
            var numeric = columns["numeric"];
            var text = columns["text"];

            // Show tooltip
            var raw_index = item.dataIndex;
            var x = numeric[item.series.xname][raw_index];
            var y = numeric[item.series.yname][raw_index];
            var id = text["id"][raw_index];
            var name = "";
            var names = text["name"];
            if (names != null)
                name = " (" + names[raw_index] + ")";
            var where = { bottom: ($(window).height() - item.pageY) + 5 };
            if (item.pageX > ($(window).width() - item.pageX)) {
                where.left = '';
                where.right = ($(window).width() - item.pageX) + 5;
            } else {
                where.left = item.pageX + 5;
                where.right = '';
            }
            $("#tooltip").html(id + name + ": (" + x + ", " + y + ")")
                         .css(where).fadeIn(200);
            tooltip_shown = true;

            // Show data values in control table
            $(".value").each(function() {
                var column_name = this.title;
                var value = "";
                if (column_name in numeric)
                    value = numeric[column_name][raw_index];
                else if (column_name in text)
                    value = text[column_name][raw_index];
                this.textContent = value;
            });
        }
    }

    function plot_selected(e, ranges) {
        sweep_select = true;
        var series = plot.getData();
        var selected = {}
        for (var i = 0; i < series.length; i++) {
            var s = series[i];
            var n = s.index;
            var axis = (n == 1) ? "axis" : n + "axis";
            var xaxis = "x" + axis;
            var yaxis = "y" + axis;
            var xstart = ranges[xaxis].from;
            var xend = ranges[xaxis].to;
            var ystart = ranges[yaxis].from;
            var yend = ranges[yaxis].to;
            var num_points = s.data.length;
            for (var j = 0; j < num_points; j++) {
                var x = s.data[j][0];
                var y = s.data[j][1];
                if (xstart <= x && x <= xend && ystart <= y && y <= yend)
                    selected[j] = true;
            }
        }
        if (Object.keys(selected).length > 0) {
            var ids = [];
            var id_col = columns["text"]["id"];
            for (var s in selected)
                ids.push(id_col[s]);
            window.location = custom_scheme + ":" + action + "?id=" +
                              ids.join(",");
        }
    }

    function mousedown(e) {
        action = e.ctrlKey ? "show_toggle" : "show_only";
        sweep_select = false;
    }

    function update_display(new_display) {
        // Update internal display state
        $.each(new_display, function () {
            display[id2index[this[0]]] = this[1];
        });
        if (plot)
            redraw_highlights(plot);
    }

    function redraw_highlights(plot) {
        // Highlight displayed models
        var series = plot.getData();
        var num_series = series.length;
        plot.unhighlight();
        $.each(display, function(i, shown) {
            if (shown) {
                for (var n = 0; n < num_series; n++)
                    plot.highlight(n, i);
            }
        });
    }

    function init() {
        var opts = {
            grid: {
                autoHighlight: false,
                hoverable: true,
                clickable: true
            },
            xaxes: [
                { position: "bottom", autoscaleMargin: null },
                { position: "top", autoscaleMargin: null },
            ],
            yaxes: [
                { position: "left", autoscaleMargin: null },
                { position: "right", autoscaleMargin: null },
            ],
            selection: {
                mode: "xy"
            },
            colors: colorbrewer.Set2[3],
            hooks: {
                draw: [ redraw_highlights ]
            }
        }
        plot = $.plot("#data", [], opts);
        $("<div id='tooltip'></div>").css({
			position: "absolute",
			display: "none",
			border: "1px solid #fdd",
			padding: "2px",
			backgroundColor: "#fee",
			opacity: 0.80
		}).appendTo("body");
        $("#data").bind("plotclick", plot_click)
                  .bind("plothover", plot_hover)
                  .bind("plotselected", plot_selected)
                  .mousedown(mousedown);
        $(".series").click(update_plot);
        $(".xaxis").change(update_plot);
        $(".yaxis").click(update_plot);
    }

    return {
        update_columns: update_columns,
        update_display: update_display,
        init: init
    }
}();

$(document).ready(vdxplot.init);
