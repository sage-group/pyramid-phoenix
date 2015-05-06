$(function() {

  // enabled tooltip
  $('[data-toggle="tooltip"]').tooltip()
  
  // MyJobs
  // ------
  
  var timerId = 0;

  // update job table with current values
  var updateJobs = function() {
     $.getJSON(
      '/myjobs/update.json',
      {},
      function(json) {
        var finished = true;
        $.each(json, function(index, job) {
            var status_class = ''
            if (job.status == 'ProcessSucceeded') {
              status_class = 'glyphicon glyphicon-ok-sign text-success';
            }
            else if (job.status == 'ProcessFailed') {
              status_class = 'glyphicon glyphicon-remove-sign text-danger';
            }
            else if (job.status == 'ProcessPaused') {
              status_class = 'glyphicon glyphicon-paused text-muted';
            }
          else if (job.status == 'ProcessStarted' || job.status == 'ProcessAccepted') {
              status_class = 'glyphicon glyphicon-cog text-muted';
              finished = false;
            }
            else {
              status_class = 'glyphicon glyphicon-question-sign text-danger';
            }

            $("#status-"+job.identifier).attr('class', status_class);
            $("#status-"+job.identifier).attr('title', job.status);
            $("#duration-"+job.identifier).text(job.duration);
            $("#progress-"+job.identifier).attr('style', "width: "+job.progress+"%");
            $("#progress-"+job.identifier).text(job.progress + "%");
        });

        if (finished == true) {
          clearInterval(timerId);
        }
      }
    );
  };

  // refresh job list each 3 secs ...
  timerId = setInterval(function() {
    updateJobs();
  }, 3000); 

  // Open publish form when publish is clicked
  $(".publish").button({
    text: false,
  }).click(function( event ) {
    var outputid = $(this).attr('data-value');
    $.getJSON(
      '/publish.output',
      {'outputid': outputid},
      function(json) {
        if (json) {
          form = $('#publish-form');
          
          // Set the title
          form.find('h3').text('Publish to Catalog Service');
          $.each(json, function(k, v) {
            // Set the value for each field from the returned json
            form.find('input[name="' + k + '"]').attr('value', v);
          });
          
          form.modal('show');
        }
      }
    );
  });

  // Open upload form when upload is clicked
  $(".upload").button({
    text: false,
  }).click(function( event ) {
    var outputid = $(this).attr('data-value');
    $.getJSON(
      '/upload.output',
      {'outputid': outputid},
      function(json) {
        if (json) {
          form = $('#upload-form');
          
          // Set the title
          form.find('h3').text('Upload to Swift Cloud');
          $.each(json, function(k, v) {
            // Set the value for each field from the returned json
            form.find('input[name="' + k + '"]').attr('value', v);
          });
          
          form.modal('show');
        }
      }
    );
  });

  // Settings
  // --------
  
  // Activate user
  $(".activate").button({
    text: false,
  }).click(function( event ) {
    var email = $(this).attr('data-value');
    $.getJSON(
      '/settings/users/'+email+'/activate.json',
      {},
      function(json) {
        location.reload();
      }
    );
  });
  
  // edit user
  $(".edit").button({
    text: false,
  }).click(function( event ) {
    var email = $(this).attr('data-value');
    $.getJSON(
      '/settings/users/'+email+'/edit.json',
      {},
      function(json) {
        if (json) {
          form = $('#user-form');
          
          // Set the title to Edit
          form.find('h3').text('Edit User');
          $.each(json, function(k, v) {
            // Set the value for each field from the returned json
            form.find('input[name="' + k + '"]').attr('value', v);
          });
          
          form.modal('show');
        }
      }
    );
  });

});