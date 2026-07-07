FROM postgres:15

COPY maintenance.sh /usr/local/bin/maintenance.sh
COPY start.sh /usr/local/bin/start.sh

RUN chmod +x /usr/local/bin/maintenance.sh /usr/local/bin/start.sh

CMD ["/usr/local/bin/start.sh"]