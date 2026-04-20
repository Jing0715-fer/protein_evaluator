// SSE Manager for Real-time Progress
(function() {
  'use strict';

  var SSEManager = {
    _connections: {},
    _handlers: {},
    _reconnectAttempts: {},
    _maxReconnectAttempts: 5,
    _reconnectDelay: 1000,

    connect: function(jobId, onMessage, onError) {
      // Disconnect existing connection
      this.disconnect(jobId);

      var url = '/api/v2/evaluate/multi/' + jobId + '/progress/stream';
      var eventSource = new EventSource(url);

      this._connections[jobId] = eventSource;
      this._handlers[jobId] = { onMessage: onMessage, onError: onError };
      this._reconnectAttempts[jobId] = 0;

      var self = this;

      eventSource.onmessage = function(event) {
        try {
          var data = JSON.parse(event.data);

          // Skip heartbeats
          if (data.type === 'heartbeat' || data.type === 'ping') {
            return;
          }

          // Call the message handler
          if (onMessage) {
            onMessage(data);
          }

          // Auto-disconnect on completion
          if (data.done || data.status === 'completed' ||
              data.status === 'failed' || data.status === 'cancelled') {
            self.disconnect(jobId);
          }
        } catch (e) {
          console.error('SSE parse error:', e);
        }
      };

      eventSource.onerror = function(err) {
        console.error('SSE error for job', jobId, ':', err);

        self.disconnect(jobId);

        // Try to reconnect with exponential backoff
        if (self._reconnectAttempts[jobId] < self._maxReconnectAttempts) {
          var delay = self._reconnectDelay * Math.pow(2, self._reconnectAttempts[jobId]);
          self._reconnectAttempts[jobId]++;

          console.log('SSE reconnecting in', delay, 'ms...');

          setTimeout(function() {
            self.connect(jobId, onMessage, onError);
          }, delay);
        } else {
          console.log('SSE max reconnect attempts reached for job', jobId);
          if (onError) {
            onError(err);
          }
        }
      };

      return eventSource;
    },

    disconnect: function(jobId) {
      if (this._connections[jobId]) {
        this._connections[jobId].close();
        delete this._connections[jobId];
      }
      if (this._handlers[jobId]) {
        delete this._handlers[jobId];
      }
      if (this._reconnectAttempts[jobId]) {
        delete this._reconnectAttempts[jobId];
      }
    },

    disconnectAll: function() {
      var self = this;
      Object.keys(this._connections).forEach(function(jobId) {
        self.disconnect(jobId);
      });
    },

    isConnected: function(jobId) {
      return !!this._connections[jobId];
    }
  };

  // Export to global
  window.SSEManager = SSEManager;
})();
