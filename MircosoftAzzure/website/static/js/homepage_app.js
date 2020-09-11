
        $(document).ready(function () {
          $("rect").each(function(index) {
            console.log("asoihjwq");
            var colorR = Math.floor((Math.random() * 256));
            var colorG = Math.floor((Math.random() * 256));
            var colorB = Math.floor((Math.random() * 256));
            $(this).attr("fill","rgb(" + colorR + "," + colorG + "," + colorB + ")");
          });
       });